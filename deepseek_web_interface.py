"""
DeepSeek网页交互模块
用于通过模拟网页操作实现DeepSeek字幕校正功能
"""

import os
import json
import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# 设置日志
logger = logging.getLogger(__name__)

class DeepSeekWebInterface:
    """DeepSeek网页交互客户端类"""

    def __init__(self, headless: bool = True, chrome_driver_path: Optional[str] = None):
        """
        初始化DeepSeek网页接口

        Args:
            headless: 是否使用无头模式
            chrome_driver_path: ChromeDriver路径，如果为None则使用系统PATH中的驱动
        """
        self.headless = headless
        self.chrome_driver_path = chrome_driver_path
        self.driver = None
        self.wait = None
        self.logged_in = False
        self.api_key = None  # 添加API密钥属性
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        
        # 确保截图目录存在
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 初始化WebDriver
        self._setup_driver()
        
    def _take_screenshot(self, name: str) -> Optional[str]:
        """
        截取当前页面截图
        
        Args:
            name: 截图名称
            
        Returns:
            截图文件路径，如果失败返回None
        """
        if not self.driver:
            return None
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            self.driver.save_screenshot(filepath)
            self.logger.info(f"截图已保存: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"截图失败: {str(e)}")
            return None
    
    def _log_error_with_screenshot(self, error_msg: str, screenshot_name: str = "error") -> None:
        """
        记录错误信息并截图
        
        Args:
            error_msg: 错误信息
            screenshot_name: 截图名称
        """
        self.logger.error(error_msg)
        screenshot_path = self._take_screenshot(screenshot_name)
        if screenshot_path:
            self.logger.error(f"错误截图: {screenshot_path}")

    def _find_api_key_input(self):
        """
        查找API密钥输入框

        Returns:
            WebElement or None: 找到的输入框元素，未找到返回None
        """
        try:
            # API密钥输入框的可能选择器（排除电话号码输入框）
            api_key_selectors = [
                # 基于type和placeholder的选择器，明确排除电话字段
                "input[type='text'][placeholder*='API']",
                "input[type='password'][placeholder*='API']",
                "input[type='text'][placeholder*='api key']",
                "input[type='password'][placeholder*='api key']",
                "input[type='text'][placeholder*='token']",
                "input[type='password'][placeholder*='token']",
                "input[type='text'][placeholder*='Token']",
                "input[type='password'][placeholder*='Token']",
                # 基于ID的选择器
                "#api-key",
                "#api_key",
                "#apiKey",
                "#token",
                "#api-token",
                # 基于class的选择器
                ".api-key-input",
                ".api_key_input",
                ".token-input",
                ".api-input",
                "input[class*='api-key']",
                "input[class*='api_key']",
                "input[class*='token']",
                "input[name*='api']",
                "input[name*='token']",
                # 通用文本输入框，但排除电话字段
                "input[type='text']:not([placeholder*='Phone']):not([placeholder*='phone']):not([type='tel'])",
                "input[type='password']:not([placeholder*='Phone']):not([placeholder*='phone'])",
            ]

            for selector in api_key_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            # 额外检查：确保这不是电话号码输入框
                            placeholder = element.get_attribute("placeholder") or ""
                            input_type = element.get_attribute("type") or ""
                            name = element.get_attribute("name") or ""

                            # 排除电话相关字段
                            if any(keyword in placeholder.lower() for keyword in ['phone', '电话', '手机', 'mobile']):
                                continue
                            if input_type == 'tel':
                                continue
                            if any(keyword in name.lower() for keyword in ['phone', 'mobile', 'telephone']):
                                continue

                            logger.info(f"找到可能的API密钥输入框: selector={selector}, placeholder={placeholder}, type={input_type}")
                            return element
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {str(e)}")
                    continue

            # 如果没找到，尝试基于页面内容查找
            all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='checkbox']):not([type='radio']):not([type='tel'])")
            logger.info(f"页面上共找到 {len(all_inputs)} 个非电话输入框")

            for i, input_elem in enumerate(all_inputs):
                try:
                    if input_elem.is_displayed() and input_elem.is_enabled():
                        placeholder = input_elem.get_attribute("placeholder") or ""
                        input_type = input_elem.get_attribute("type") or ""
                        name = input_elem.get_attribute("name") or ""

                        # 详细记录输入框信息
                        logger.info(f"输入框 {i+1}: type={input_type}, name={name}, placeholder={placeholder}")

                        # 寻找与API相关的输入框
                        if any(keyword in placeholder.lower() for keyword in ['api', 'key', 'token', '密钥', '令牌']):
                            logger.info(f"通过placeholder找到API密钥输入框: {placeholder}")
                            return input_elem
                        if any(keyword in name.lower() for keyword in ['api', 'key', 'token']):
                            logger.info(f"通过name找到API密钥输入框: {name}")
                            return input_elem
                        # 如果是普通的文本或密码输入框，也可能是API密钥输入框
                        elif input_type in ['text', 'password'] and not placeholder:
                            logger.info(f"找到无标识的文本/密码输入框，可能是API密钥输入框")
                            return input_elem
                except Exception as e:
                    logger.debug(f"检查输入框 {i+1} 时出错: {str(e)}")
                    continue

            logger.warning("未找到任何合适的API密钥输入框")
            return None

        except Exception as e:
            logger.error(f"查找API密钥输入框时出错: {str(e)}")
            return None

    def _click_api_key_confirm_button(self):
        """
        查找并点击API密钥确认按钮

        Returns:
            bool: 是否成功点击按钮
        """
        try:
            # API密钥确认按钮的可能选择器
            confirm_button_selectors = [
                # 基于文本内容的选择器（使用XPath）
                "//button[contains(text(), '确认')]",
                "//button[contains(text(), '提交')]",
                "//button[contains(text(), '验证')]",
                "//button[contains(text(), 'Confirm')]",
                "//button[contains(text(), 'Submit')]",
                "//button[contains(text(), 'Verify')]",
                "//button[contains(text(), '登录')]",
                "//button[contains(text(), 'Login')]",
                "//button[contains(text(), 'Sign in')]",
                # 基于type的选择器
                "button[type='submit']",
                "input[type='submit']",
                # 基于class的选择器
                ".btn-primary",
                ".btn-submit",
                ".confirm-button",
                ".submit-button",
                ".login-button",
                ".api-key-submit",
                "button[class*='primary']",
                "button[class*='submit']",
                "button[class*='confirm']",
                # Ant Design组件
                ".ant-btn-primary",
                ".ant-btn",
                # Element UI组件
                ".el-button--primary",
                ".el-button",
            ]

            for selector in confirm_button_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath选择器
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS选择器
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            element_text = element.text or ""
                            logger.info(f"找到确认按钮: selector={selector}, text='{element_text}'")
                            element.click()
                            logger.info("成功点击确认按钮")
                            return True
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 失败: {str(e)}")
                    continue

            # 如果没找到专门按钮，尝试任何可点击的按钮
            logger.info("未找到专门的确认按钮，尝试查找任何可点击的按钮...")
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"页面上共找到 {len(all_buttons)} 个按钮")

            for i, button in enumerate(all_buttons):
                try:
                    if button.is_displayed() and button.is_enabled():
                        button_text = button.text or ""
                        button_class = button.get_attribute("class") or ""
                        logger.info(f"按钮 {i+1}: text='{button_text}', class='{button_class}'")

                        # 排除明显的无关按钮
                        if any(keyword in button_text.lower() for keyword in ['cancel', '取消', 'back', '返回', 'help', '帮助']):
                            continue

                        button.click()
                        logger.info(f"点击了按钮 {i+1}: {button_text}")
                        time.sleep(2)  # 等待页面响应

                        # 检查是否有页面变化
                        current_url = self.driver.current_url
                        logger.info(f"点击按钮后URL: {current_url}")

                        return True
                except Exception as e:
                    logger.debug(f"点击按钮 {i+1} 时出错: {str(e)}")
                    continue

            logger.warning("未找到任何可点击的确认按钮")
            return False

        except Exception as e:
            logger.error(f"点击确认按钮时出错: {str(e)}")
            return False

    def _check_chat_access(self):
        """
        检查是否可以访问聊天功能

        Returns:
            bool: 是否可以访问聊天功能
        """
        try:
            # 检查页面是否包含聊天相关的元素
            chat_indicators = [
                "textarea",  # 聊天输入框
                ".chat-input",
                ".message-input",
                ".chat-container",
                ".chat-window",
                "[class*='chat']",
                "[class*='message']",
                "textarea[placeholder*='输入']",
                "textarea[placeholder*='message']",
                "textarea[placeholder*='chat']",
            ]

            for selector in chat_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            logger.info(f"找到聊天功能指示器: {selector}")
                            return True
                except Exception:
                    continue

            # 检查页面标题是否包含聊天相关内容
            try:
                title = self.driver.title.lower()
                if any(keyword in title for keyword in ['chat', '聊天', 'deepseek']):
                    logger.info(f"通过页面标题检测到聊天功能: {title}")
                    return True
            except Exception:
                pass

            logger.info("未检测到聊天功能")
            return False

        except Exception as e:
            logger.error(f"检查聊天访问权限时出错: {str(e)}")
            return False

    def _setup_driver(self) -> bool:
        """
        设置Chrome WebDriver

        Returns:
            bool: 设置是否成功
        """
        try:
            # 配置Chrome选项
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # 添加常用选项
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            
            # 禁用图片加载以提高速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # 初始化WebDriver
            if self.chrome_driver_path:
                service = Service(self.chrome_driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                self.driver = webdriver.Chrome(options=chrome_options)
            
            # 设置显式等待
            self.wait = WebDriverWait(self.driver, 10)
            
            logger.info("Chrome WebDriver初始化成功")
            return True
            
        except WebDriverException as e:
            logger.error(f"Chrome WebDriver初始化失败: {e}")
            return False
        except Exception as e:
            logger.error(f"设置WebDriver时发生异常: {e}")
            return False

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        登录DeepSeek官网

        Args:
            username: DeepSeek账号用户名
            password: DeepSeek账号密码

        Returns:
            Dict[str, Any]: 登录结果
        """
        try:
            # 初始化WebDriver（如果尚未初始化）
            if not self.driver:
                if not self._setup_driver():
                    return {
                        "success": False,
                        "error": "WebDriver初始化失败"
                    }

            # 访问DeepSeek登录页面
            logger.info("正在访问DeepSeek登录页面...")
            self.driver.get("https://platform.deepseek.com/login")
            
            # 等待页面加载
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)  # 额外等待确保页面完全加载
            
            # 查找并填写用户名
            try:
                # 尝试多种可能的用户名输入框定位方式
                username_selectors = [
                    "input[name='username']",
                    "input[name='email']",
                    "input[type='email']",
                    "input[placeholder*='邮箱']",
                    "input[placeholder*='用户名']",
                    "input[placeholder*='账号']",
                    "#username",
                    "#email"
                ]
                
                username_input = None
                for selector in username_selectors:
                    try:
                        username_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not username_input:
                    # 如果上述方法都不行，尝试通过XPath查找
                    username_input = self.driver.find_element(By.XPATH, "//input[contains(@placeholder, '邮箱') or contains(@placeholder, '用户名') or contains(@placeholder, '账号') or @name='username' or @name='email']")
                
                username_input.clear()
                username_input.send_keys(username)
                logger.info("用户名填写成功")
                
            except NoSuchElementException as e:
                logger.error(f"找不到用户名输入框: {e}")
                return {
                    "success": False,
                    "error": "找不到用户名输入框，可能是页面结构已更改"
                }
            
            # 查找并填写密码
            try:
                password_selectors = [
                    "input[name='password']",
                    "input[type='password']",
                    "input[placeholder*='密码']",
                    "#password"
                ]
                
                password_input = None
                for selector in password_selectors:
                    try:
                        password_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not password_input:
                    password_input = self.driver.find_element(By.XPATH, "//input[contains(@placeholder, '密码') or @name='password']")
                
                password_input.clear()
                password_input.send_keys(password)
                logger.info("密码填写成功")
                
            except NoSuchElementException as e:
                logger.error(f"找不到密码输入框: {e}")
                return {
                    "success": False,
                    "error": "找不到密码输入框，可能是页面结构已更改"
                }
            
            # 查找并点击登录按钮
            try:
                login_button_selectors = [
                    "button[type='submit']",
                    "button.btn-primary",
                    "button.login-btn",
                    ".login-button",
                    "#login-button",
                    ".auth-button",
                    "button:contains('登录')",
                    "button:contains('登陆')",
                    "button:contains('Sign in')",
                    "button:contains('Log in')",
                    "input[type='submit']"
                ]
                
                login_button = None
                for selector in login_button_selectors:
                    try:
                        if ":contains(" in selector:
                            # 使用XPath查找包含特定文本的按钮
                            text = selector.split("'")[1]
                            login_button = self.driver.find_element(By.XPATH, f"//button[contains(text(), '{text}')]")
                        else:
                            login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not login_button:
                    # 尝试通过XPath查找包含登录相关文本的按钮
                    login_button = self.driver.find_element(By.XPATH, "//button[contains(text(), '登录') or contains(text(), '登陆') or contains(text(), 'Sign in') or contains(text(), 'Log in') or contains(@class, 'login') or contains(@class, 'auth')]")
                
                login_button.click()
                logger.info("登录按钮点击成功")
                
            except NoSuchElementException as e:
                logger.error(f"找不到登录按钮: {e}")
                return {
                    "success": False,
                    "error": "找不到登录按钮，可能是页面结构已更改"
                }
            
            # 等待登录完成
            time.sleep(5)
            
            # 检查是否登录成功（通过URL变化或页面元素）
            current_url = self.driver.current_url
            if "login" not in current_url.lower():
                self.logged_in = True
                logger.info("DeepSeek登录成功")
                return {
                    "success": True,
                    "message": "登录成功"
                }
            else:
                # 检查是否有错误消息
                try:
                    error_elements = self.driver.find_elements(By.CSS_SELECTOR, ".error, .alert-danger, .text-danger")
                    if error_elements:
                        error_message = error_elements[0].text
                        return {
                            "success": False,
                            "error": f"登录失败: {error_message}"
                        }
                except:
                    pass
                
                return {
                    "success": False,
                    "error": "登录失败，请检查用户名和密码"
                }
                
        except TimeoutException:
            logger.error("登录页面加载超时")
            return {
                "success": False,
                "error": "登录页面加载超时，请检查网络连接"
            }
        except Exception as e:
            # 确保错误信息是字符串格式
            if isinstance(e, dict):
                error_message = json.dumps(e, ensure_ascii=False)
            else:
                error_message = str(e)
            
            self._log_error_with_screenshot(f"登录失败: {error_message}", "login_error")
            return {
                "success": False,
                "error": f"登录失败: {error_message}"
            }

    def login_with_api_key(self, api_key: str) -> Dict[str, Any]:
        """
        使用API密钥进行认证

        Args:
            api_key: DeepSeek API密钥

        Returns:
            Dict[str, Any]: 登录结果
        """
        try:
            # 初始化WebDriver
            if not self.driver:
                if not self._setup_driver():
                    return {
                        "success": False,
                        "error": "WebDriver初始化失败"
                    }

            # 首先尝试直接访问API密钥验证页面
            logger.info("正在尝试通过API密钥进行认证...")

            # 尝试多个可能的API认证URL
            api_auth_urls = [
                "https://platform.deepseek.com/api_keys",  # API密钥管理页面
                "https://platform.deepseek.com/chat",      # 聊天页面
                "https://chat.deepseek.com",               # 直接聊天页面
            ]

            auth_success = False
            last_error = None

            for url in api_auth_urls:
                try:
                    logger.info(f"尝试访问: {url}")
                    self.driver.get(url)

                    # 等待页面加载
                    self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    time.sleep(3)  # 额外等待确保页面完全加载

                    current_url = self.driver.current_url
                    logger.info(f"访问后当前URL: {current_url}")

                    # 检查是否被重定向到登录页面
                    if "sign_in" in current_url.lower():
                        logger.warning(f"访问 {url} 被重定向到登录页面")
                        continue

                    # 尝试在此页面查找API密钥输入框
                    api_key_input = self._find_api_key_input()
                    if api_key_input:
                        logger.info("找到API密钥输入框，开始输入密钥...")
                        api_key_input.clear()
                        api_key_input.send_keys(api_key)
                        logger.info("API密钥填写成功")

                        # 查找并点击确认按钮
                        if self._click_api_key_confirm_button():
                            time.sleep(5)  # 等待认证完成
                            current_url_after_auth = self.driver.current_url
                            logger.info(f"认证后当前URL: {current_url_after_auth}")

                            if "sign_in" not in current_url_after_auth.lower():
                                auth_success = True
                                break

                    # 如果没有找到API密钥输入框，检查是否已经可以访问聊天功能
                    elif self._check_chat_access():
                        logger.info("可以直接访问聊天功能，认证可能已经有效")
                        auth_success = True
                        break

                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"尝试访问 {url} 失败: {last_error}")
                    continue

            if not auth_success:
                logger.error("所有API认证尝试都失败了")
                self.close()  # 清理资源
                return {
                    "success": False,
                    "error": f"API密钥认证失败，最后错误: {last_error}"
                }

            # 设置登录状态，保存API密钥
            self.logged_in = True
            self.api_key = api_key
            logger.info("API密钥认证成功")

            return {
                "success": True,
                "message": "API密钥认证成功"
            }
            
            # 尝试在页面中设置API密钥
            try:
                # 查找API密钥输入框
                api_key_selectors = [
                    "input[name='api_key']",
                    "input[placeholder*='API']",
                    "input[placeholder*='密钥']",
                    "input[placeholder*='key']",
                    ".api-key-input",
                    "#api-key"
                ]
                
                api_key_input = None
                for selector in api_key_selectors:
                    try:
                        api_key_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if api_key_input:
                    # 如果找到API密钥输入框，则输入密钥
                    api_key_input.clear()
                    api_key_input.send_keys(api_key)
                    logger.info("API密钥填写成功")
                    
                    # 查找并点击确认按钮
                    confirm_button_selectors = [
                        "button[type='submit']",
                        "button.btn-primary",
                        ".confirm-button",
                        "#confirm-api-key"
                    ]
                    
                    confirm_button = None
                    for selector in confirm_button_selectors:
                        try:
                            confirm_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            break
                        except NoSuchElementException:
                            continue
                    
                    if confirm_button:
                        confirm_button.click()
                        time.sleep(3)  # 等待认证完成
                else:
                    # 如果没有找到API密钥输入框，可能页面已经通过其他方式认证
                    # 尝试直接访问聊天页面，看看是否已经认证
                    logger.info("未找到API密钥输入框，尝试直接访问聊天页面...")
                    try:
                        self.driver.get("https://platform.deepseek.com/chat")
                        time.sleep(3)  # 等待页面加载
                        
                        # 检查是否成功访问聊天页面
                        current_url = self.driver.current_url
                        logger.info(f"当前URL: {current_url}")
                        
                        # 检查是否被重定向到登录页面
                        if "sign_in" in current_url.lower():
                            logger.info("被重定向到登录页面，尝试直接访问API密钥页面...")
                            # 先尝试直接访问API密钥页面
                            try:
                                logger.info("尝试直接访问API密钥页面: https://platform.deepseek.com/api_keys")
                                self.driver.get("https://platform.deepseek.com/api_keys")
                                time.sleep(5)  # 等待页面加载
                                
                                # 检查是否成功访问API密钥页面
                                current_url = self.driver.current_url
                                logger.info(f"访问API密钥页面后的URL: {current_url}")
                                
                                # 如果成功访问API密钥页面，尝试查找API密钥输入框
                                if "api_keys" in current_url.lower() or "api-key" in current_url.lower():
                                    logger.info("成功访问API密钥页面，尝试查找API密钥输入框...")
                                else:
                                    logger.info("未能直接访问API密钥页面，尝试使用API密钥登录...")
                            except Exception as e:
                                logger.warning(f"直接访问API密钥页面失败: {e}")
                                logger.info("尝试使用API密钥登录...")
                            
                            # 尝试使用API密钥登录
                            try:
                                # 先尝试点击可能显示API密钥输入框的按钮或链接
                                logger.info("开始查找API密钥切换按钮...")
                                api_key_toggle_selectors = [
                                    # 文本内容选择器 - 使用XPath
                                    "//button[contains(text(), 'API')]",
                                    "//button[contains(text(), '密钥')]",
                                    "//button[contains(text(), 'Token')]",
                                    "//a[contains(text(), 'API')]",
                                    "//a[contains(text(), '密钥')]",
                                    "//a[contains(text(), 'Token')]",
                                    "//button[contains(text(), '使用API密钥')]",
                                    "//button[contains(text(), 'API Key')]",
                                    "//a[contains(text(), '使用API密钥')]",
                                    "//a[contains(text(), 'API Key')]",
                                    "//button[contains(text(), 'API密钥登录')]",
                                    "//a[contains(text(), 'API密钥登录')]",
                                    "//button[contains(text(), 'Token登录')]",
                                    "//a[contains(text(), 'Token登录')]",
                                    "//button[contains(text(), '使用Token')]",
                                    "//a[contains(text(), '使用Token')]",
                                    # CSS类选择器
                                    ".api-key-toggle",
                                    ".token-tab",
                                    ".api-tab",
                                    "button[class*='api']",
                                    "button[class*='token']",
                                    "a[class*='api']",
                                    "a[class*='token']",
                                    # 通用按钮和链接
                                    "//button[contains(@class, 'tab')]",
                                    "//a[contains(@class, 'tab')]",
                                    "//button[contains(@class, 'switch')]",
                                    "//a[contains(@class, 'switch')]",
                                    "//button[contains(@class, 'toggle')]",
                                    "//a[contains(@class, 'toggle')]"
                                ]
                                
                                found_toggle = False
                                # 先尝试点击可能显示API密钥输入框的按钮或链接
                                for toggle_selector in api_key_toggle_selectors:
                                    try:
                                        if toggle_selector.startswith("//"):
                                            # XPath选择器
                                            toggle_elements = self.driver.find_elements(By.XPATH, toggle_selector)
                                        else:
                                            # CSS选择器
                                            toggle_elements = self.driver.find_elements(By.CSS_SELECTOR, toggle_selector)
                                        
                                        for toggle_element in toggle_elements:
                                            if toggle_element and toggle_element.is_displayed():
                                                logger.info(f"找到API密钥切换按钮: {toggle_selector}")
                                                toggle_element.click()
                                                time.sleep(2)  # 等待页面更新
                                                found_toggle = True
                                                break
                                    except Exception as e:
                                        logger.debug(f"尝试选择器 {toggle_selector} 失败: {str(e)}")
                                        continue
                                
                                if not found_toggle:
                                    logger.info("未找到任何API密钥切换按钮")
                                
                                # 尝试查找所有按钮和链接，以便调试
                                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                                all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                                all_spans = self.driver.find_elements(By.TAG_NAME, "span")
                                logger.info(f"页面上共找到 {len(all_buttons)} 个按钮, {len(all_links)} 个链接, {len(all_divs)} 个div, {len(all_spans)} 个span")
                                
                                # 记录前几个按钮和链接的文本内容
                                for i, button in enumerate(all_buttons[:5]):
                                    try:
                                        button_text = button.text or "无文本"
                                        button_class = button.get_attribute("class") or "无类"
                                        logger.info(f"按钮 {i+1}: 文本='{button_text}', 类='{button_class}'")
                                    except Exception as e:
                                        logger.info(f"按钮 {i+1}: 获取属性时出错: {str(e)}")
                                
                                for i, link in enumerate(all_links[:5]):
                                    try:
                                        link_text = link.text or "无文本"
                                        link_class = link.get_attribute("class") or "无类"
                                        logger.info(f"链接 {i+1}: 文本='{link_text}', 类='{link_class}'")
                                    except Exception as e:
                                        logger.info(f"链接 {i+1}: 获取属性时出错: {str(e)}")
                                
                                # 检查div和span元素，查找可能的API密钥切换元素
                                for i, div in enumerate(all_divs[:10]):
                                    try:
                                        div_text = div.text or "无文本"
                                        div_class = div.get_attribute("class") or "无类"
                                        if any(keyword in div_text.lower() for keyword in ['api', '密钥', 'token', 'key']):
                                            logger.info(f"可能相关的div {i+1}: 文本='{div_text}', 类='{div_class}'")
                                            # 尝试点击这个div
                                            try:
                                                if div.is_displayed() and div.is_enabled():
                                                    div.click()
                                                    logger.info(f"点击了div {i+1}")
                                                    time.sleep(2)
                                                    break
                                            except Exception as e:
                                                logger.info(f"点击div {i+1}失败: {str(e)}")
                                    except Exception as e:
                                        logger.info(f"div {i+1}: 获取属性时出错: {str(e)}")
                                
                                for i, span in enumerate(all_spans[:10]):
                                    try:
                                        span_text = span.text or "无文本"
                                        span_class = span.get_attribute("class") or "无类"
                                        if any(keyword in span_text.lower() for keyword in ['api', '密钥', 'token', 'key']):
                                            logger.info(f"可能相关的span {i+1}: 文本='{span_text}', 类='{span_class}'")
                                            # 尝试点击这个span
                                            try:
                                                if span.is_displayed() and span.is_enabled():
                                                    span.click()
                                                    logger.info(f"点击了span {i+1}")
                                                    time.sleep(2)
                                                    break
                                            except Exception as e:
                                                logger.info(f"点击span {i+1}失败: {str(e)}")
                                    except Exception as e:
                                        logger.info(f"span {i+1}: 获取属性时出错: {str(e)}")
                                
                                # 尝试使用JavaScript查找并点击可能包含API、密钥或Token文本的元素
                                try:
                                    api_elements = self.driver.execute_script("""
                                        var elements = [];
                                        var allElements = document.querySelectorAll('*');
                                        for (var i = 0; i < allElements.length; i++) {
                                            var element = allElements[i];
                                            var text = element.textContent || '';
                                            if (text.toLowerCase().includes('api') || 
                                                text.toLowerCase().includes('密钥') || 
                                                text.toLowerCase().includes('token') || 
                                                text.toLowerCase().includes('key')) {
                                                elements.push({
                                                    tagName: element.tagName,
                                                    text: text.substring(0, 50),
                                                    className: element.className || '',
                                                    id: element.id || ''
                                                });
                                            }
                                        }
                                        return elements;
                                    """)
                                    
                                    logger.info(f"JavaScript找到 {len(api_elements)} 个可能相关的元素")
                                    for i, elem in enumerate(api_elements[:5]):
                                        logger.info(f"JS元素 {i+1}: 标签={elem['tagName']}, 文本='{elem['text']}', 类='{elem['className']}', ID='{elem['id']}'")
                                except Exception as e:
                                    logger.info(f"JavaScript查找元素失败: {str(e)}")
                                
                                # 查找API密钥输入框
                                api_key_input_selectors = [
                                    # API密钥页面特定选择器
                                    "input[name='api_key']",
                                    "input[placeholder*='API']",
                                    "input[placeholder*='密钥']",
                                    "input[placeholder*='key']",
                                    "input[placeholder*='Token']",
                                    "input[placeholder*='token']",
                                    "input[aria-label*='API']",
                                    "input[aria-label*='密钥']",
                                    "input[aria-label*='key']",
                                    "input[aria-label*='Token']",
                                    "input[aria-label*='token']",
                                    # 通用输入框选择器
                                    ".api-key-input",
                                    "#api-key",
                                    "input[type='password']",
                                    "input[type='text']",
                                    "input[name='token']",
                                    "input.form-control",
                                    "input.ant-input",
                                    ".ant-input",
                                    "input.el-input__inner",
                                    ".el-input__inner",
                                    # 更广泛的选择器
                                    "input:not([type='checkbox']):not([type='radio'])",
                                    "input[autocomplete*='key']",
                                    "input[autocomplete*='token']"
                                ]
                                
                                # 尝试查找所有输入框，以便调试
                                all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                                logger.info(f"页面上共找到 {len(all_inputs)} 个输入框")
                                for i, inp in enumerate(all_inputs[:5]):  # 只记录前5个输入框的信息
                                    try:
                                        input_type = inp.get_attribute("type") or "未知"
                                        input_name = inp.get_attribute("name") or "无"
                                        input_placeholder = inp.get_attribute("placeholder") or "无"
                                        input_id = inp.get_attribute("id") or "无"
                                        input_class = inp.get_attribute("class") or "无"
                                        logger.info(f"输入框 {i+1}: type={input_type}, name={input_name}, placeholder={input_placeholder}, id={input_id}, class={input_class}")
                                    except Exception as e:
                                        logger.info(f"输入框 {i+1}: 获取属性时出错: {str(e)}")
                                
                                api_key_input = None
                                input_details = []
                                
                                # 尝试查找所有输入框，以便调试
                                all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                                logger.info(f"页面上共找到 {len(all_inputs)} 个输入框")
                                
                                # 记录所有输入框的详细信息
                                for i, inp in enumerate(all_inputs):
                                    try:
                                        input_type = inp.get_attribute("type") or "未知"
                                        input_name = inp.get_attribute("name") or "无"
                                        input_placeholder = inp.get_attribute("placeholder") or "无"
                                        input_id = inp.get_attribute("id") or "无"
                                        input_class = inp.get_attribute("class") or "无"
                                        input_value = inp.get_attribute("value") or "无"
                                        input_aria_label = inp.get_attribute("aria-label") or "无"
                                        input_autocomplete = inp.get_attribute("autocomplete") or "无"
                                        
                                        # 检查是否是可见的输入框
                                        is_displayed = inp.is_displayed()
                                        is_enabled = inp.is_enabled()
                                        
                                        # 记录输入框详细信息
                                        input_info = {
                                            "index": i,
                                            "type": input_type,
                                            "name": input_name,
                                            "placeholder": input_placeholder,
                                            "id": input_id,
                                            "class": input_class,
                                            "value": input_value,
                                            "aria_label": input_aria_label,
                                            "autocomplete": input_autocomplete,
                                            "is_displayed": is_displayed,
                                            "is_enabled": is_enabled
                                        }
                                        input_details.append(input_info)
                                        
                                        # 记录前5个输入框的信息
                                        if i < 5:
                                            logger.info(f"输入框 {i+1}: type={input_type}, name={input_name}, placeholder={input_placeholder}, id={input_id}, class={input_class}, value={input_value}, aria-label={input_aria_label}, autocomplete={input_autocomplete}, displayed={is_displayed}, enabled={is_enabled}")
                                    except Exception as e:
                                        logger.info(f"输入框 {i+1}: 获取属性时出错: {str(e)}")
                                
                                # 尝试使用选择器查找API密钥输入框
                                for selector in api_key_input_selectors:
                                    try:
                                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                        for element in elements:
                                            if element.is_displayed() and element.is_enabled():
                                                api_key_input = element
                                                logger.info(f"找到可见的输入框: {selector}")
                                                break
                                        if api_key_input:
                                            break
                                    except Exception as e:
                                        logger.debug(f"尝试选择器 {selector} 失败: {str(e)}")
                                        continue
                                
                                # 如果没有找到输入框，尝试使用更通用的方法
                                if not api_key_input:
                                    logger.info("使用选择器未找到输入框，尝试检查所有输入框...")
                                    for input_info in input_details:
                                        if input_info["is_displayed"] and input_info["is_enabled"]:
                                            # 检查输入框的各种属性是否包含API密钥相关关键词
                                            attrs_to_check = [
                                                input_info["name"].lower(),
                                                input_info["placeholder"].lower(),
                                                input_info["id"].lower(),
                                                input_info["class"].lower(),
                                                input_info["aria_label"].lower(),
                                                input_info["autocomplete"].lower()
                                            ]
                                            
                                            for attr in attrs_to_check:
                                                if any(keyword in attr for keyword in ['api', '密钥', 'token', 'key']):
                                                    logger.info(f"通过属性检查找到可能的API密钥输入框: {input_info}")
                                                    api_key_input = all_inputs[input_info["index"]]
                                                    break
                                            
                                            if api_key_input:
                                                break
                                
                                # 如果还是没有找到输入框，尝试使用JavaScript查找
                                if not api_key_input:
                                    logger.info("使用常规方法未找到输入框，尝试使用JavaScript查找...")
                                    try:
                                        js_result = self.driver.execute_script("""
                                            var inputs = document.querySelectorAll('input');
                                            var candidates = [];
                                            
                                            for (var i = 0; i < inputs.length; i++) {
                                                var input = inputs[i];
                                                if (!input.disabled && input.offsetParent !== null) {
                                                    var attrs = {
                                                        index: i,
                                                        type: input.type || '',
                                                        name: input.name || '',
                                                        placeholder: input.placeholder || '',
                                                        id: input.id || '',
                                                        className: input.className || '',
                                                        ariaLabel: input.getAttribute('aria-label') || '',
                                                        autocomplete: input.getAttribute('autocomplete') || ''
                                                    };
                                                    
                                                    var text = (attrs.name + ' ' + attrs.placeholder + ' ' + attrs.id + ' ' + attrs.className + ' ' + attrs.ariaLabel + ' ' + attrs.autocomplete).toLowerCase();
                                                    if (text.includes('api') || text.includes('密钥') || text.includes('token') || text.includes('key')) {
                                                        candidates.push(attrs);
                                                    }
                                                }
                                            }
                                            
                                            return candidates;
                                        """)
                                        
                                        logger.info(f"JavaScript找到 {len(js_result)} 个可能的API密钥输入框")
                                        for i, candidate in enumerate(js_result):
                                            logger.info(f"JS候选输入框 {i+1}: {candidate}")
                                            if i == 0:  # 使用第一个候选
                                                api_key_input = all_inputs[candidate["index"]]
                                                break
                                    except Exception as e:
                                        logger.info(f"JavaScript查找输入框失败: {str(e)}")
                                
                                # 如果还是没有找到输入框，尝试使用第一个可见的文本输入框
                                if not api_key_input:
                                    logger.info("使用所有方法都未找到API密钥输入框，尝试使用第一个可见的文本输入框...")
                                    for input_info in input_details:
                                        if input_info["is_displayed"] and input_info["is_enabled"]:
                                            if input_info["type"] in ["text", "password", ""] or input_info["type"] == "未知":
                                                logger.info(f"使用第一个可见的文本输入框: {input_info}")
                                                api_key_input = all_inputs[input_info["index"]]
                                                break
                                
                                if api_key_input:
                                    # 如果找到输入框，则输入API密钥
                                    api_key_input.clear()
                                    api_key_input.send_keys(api_key)
                                    logger.info("API密钥填写成功")
                                    
                                    # 查找并点击登录/提交按钮
                                    login_button_selectors = [
                                        # API密钥页面特定选择器
                                        "button[type='submit']",
                                        "button.btn-primary",
                                        ".login-button",
                                        "#login-button",
                                        ".submit-button",
                                        "#submit-button",
                                        "button.btn",
                                        "button.ant-btn",
                                        ".ant-btn-primary",
                                        "button.el-button",
                                        ".el-button--primary",
                                        # 文本内容选择器
                                        "button:contains('登录')",
                                        "button:contains('Login')",
                                        "button:contains('Sign in')",
                                        "button:contains('Sign In')",
                                        "button:contains('登入')",
                                        "button:contains('提交')",
                                        "button:contains('Submit')",
                                        "button:contains('验证')",
                                        "button:contains('Verify')",
                                        "button:contains('确认')",
                                        "button:contains('Confirm')",
                                        # 类名选择器
                                        "button[class*='login']",
                                        "button[class*='submit']",
                                        "button[class*='primary']",
                                        "button[class*='signin']",
                                        "button[class*='sign-in']",
                                        "button[class*='confirm']",
                                        "button[class*='verify']",
                                        # 通用选择器
                                        "input[type='submit']",
                                        ".submit",
                                        "#submit",
                                        "button:not([disabled])"
                                    ]
                                    
                                    login_button = None
                                    button_details = []
                                    
                                    # 尝试查找所有按钮和可点击元素，以便调试
                                    all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                                    all_anchors = self.driver.find_elements(By.TAG_NAME, "a")
                                    all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                                    all_spans = self.driver.find_elements(By.TAG_NAME, "span")
                                    all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                                    
                                    # 合并所有可点击元素
                                    all_clickable_elements = all_buttons + all_anchors + all_divs + all_spans + all_inputs
                                    
                                    logger.info(f"页面上共找到 {len(all_buttons)} 个按钮, {len(all_anchors)} 个链接, {len(all_divs)} 个div, {len(all_spans)} 个span, {len(all_inputs)} 个输入框")
                                    
                                    # 记录所有可点击元素的详细信息
                                    for i, element in enumerate(all_clickable_elements):
                                        try:
                                            tag_name = element.tag_name
                                            element_text = element.text or "无文本"
                                            element_type = element.get_attribute("type") or "无"
                                            element_class = element.get_attribute("class") or "无"
                                            element_id = element.get_attribute("id") or "无"
                                            element_name = element.get_attribute("name") or "无"
                                            element_href = element.get_attribute("href") or "无"
                                            element_role = element.get_attribute("role") or "无"
                                            element_aria_label = element.get_attribute("aria-label") or "无"
                                            element_onclick = element.get_attribute("onclick") or "无"
                                            
                                            # 检查是否是可见的元素
                                            is_displayed = element.is_displayed()
                                            is_enabled = element.is_enabled() if element.tag_name == "button" or element.tag_name == "input" else True
                                            
                                            # 记录元素详细信息
                                            element_info = {
                                                "index": i,
                                                "tag_name": tag_name,
                                                "text": element_text,
                                                "type": element_type,
                                                "class": element_class,
                                                "id": element_id,
                                                "name": element_name,
                                                "href": element_href,
                                                "role": element_role,
                                                "aria_label": element_aria_label,
                                                "onclick": element_onclick,
                                                "is_displayed": is_displayed,
                                                "is_enabled": is_enabled
                                            }
                                            button_details.append(element_info)
                                            
                                            # 记录前10个元素的信息
                                            if i < 10:
                                                logger.info(f"元素 {i+1} ({tag_name}): text='{element_text}', type={element_type}, class={element_class}, id={element_id}, name={element_name}, href={element_href}, role={element_role}, aria-label={element_aria_label}, onclick={element_onclick}, displayed={is_displayed}, enabled={is_enabled}")
                                        except Exception as e:
                                            logger.info(f"元素 {i+1}: 获取属性时出错: {str(e)}")
                                    
                                    # 尝试使用选择器查找登录按钮
                                    for selector in login_button_selectors:
                                        try:
                                            if ":contains" in selector:
                                                # 对于包含:contains的选择器，使用XPath
                                                text = selector.split(":contains('")[1].split("')")[0]
                                                xpath = f"//button[contains(text(), '{text}')]"
                                                elements = self.driver.find_elements(By.XPATH, xpath)
                                                for element in elements:
                                                    if element.is_displayed() and element.is_enabled():
                                                        login_button = element
                                                        logger.info(f"找到可见的登录按钮: {selector}")
                                                        break
                                            else:
                                                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                                for element in elements:
                                                    if element.is_displayed() and element.is_enabled():
                                                        login_button = element
                                                        logger.info(f"找到可见的登录按钮: {selector}")
                                                        break
                                            if login_button:
                                                break
                                        except Exception as e:
                                            logger.debug(f"尝试选择器 {selector} 失败: {str(e)}")
                                            continue
                                    
                                    # 如果没有找到按钮，尝试使用更通用的方法
                                    if not login_button:
                                        logger.info("使用选择器未找到登录按钮，尝试检查所有可点击元素...")
                                        for element_info in button_details:
                                            if element_info["is_displayed"] and element_info["is_enabled"]:
                                                # 检查元素的各种属性是否包含登录相关关键词
                                                attrs_to_check = [
                                                    element_info["text"].lower(),
                                                    element_info["class"].lower(),
                                                    element_info["id"].lower(),
                                                    element_info["name"].lower(),
                                                    element_info["role"].lower(),
                                                    element_info["aria_label"].lower(),
                                                    element_info["onclick"].lower()
                                                ]
                                                
                                                for attr in attrs_to_check:
                                                    if any(keyword in attr for keyword in ['登录', 'login', 'signin', 'sign in', '提交', 'submit', '确认', 'confirm', '验证', 'verify', 'continue', 'next', 'save', 'done']):
                                                        logger.info(f"通过属性检查找到可能的登录按钮: {element_info}")
                                                        login_button = all_clickable_elements[element_info["index"]]
                                                        break
                                                
                                                if login_button:
                                                    break
                                    
                                    # 如果还是没有找到按钮，尝试使用JavaScript查找
                                    if not login_button:
                                        logger.info("使用常规方法未找到登录按钮，尝试使用JavaScript查找...")
                                        try:
                                            js_result = self.driver.execute_script("""
                                                var elements = document.querySelectorAll('button, a, div, span, input');
                                                var candidates = [];
                                                
                                                for (var i = 0; i < elements.length; i++) {
                                                    var element = elements[i];
                                                    var isButton = element.tagName === 'BUTTON';
                                                    var isLink = element.tagName === 'A';
                                                    var isInput = element.tagName === 'INPUT';
                                                    var isDiv = element.tagName === 'DIV';
                                                    var isSpan = element.tagName === 'SPAN';
                                                    
                                                    // 检查元素是否可见且可点击
                                                    if ((isButton && !element.disabled) || 
                                                        (isLink && element.href) || 
                                                        (isInput && element.type === 'submit') ||
                                                        (isDiv || isSpan)) {
                                                        
                                                        if (element.offsetParent !== null) {
                                                            var attrs = {
                                                                index: i,
                                                                tagName: element.tagName,
                                                                text: element.textContent || '',
                                                                className: element.className || '',
                                                                id: element.id || '',
                                                                name: element.name || '',
                                                                role: element.getAttribute('role') || '',
                                                                ariaLabel: element.getAttribute('aria-label') || '',
                                                                onclick: element.getAttribute('onclick') || ''
                                                            };
                                                            
                                                            var text = (attrs.text + ' ' + attrs.className + ' ' + attrs.id + ' ' + attrs.name + ' ' + attrs.role + ' ' + attrs.ariaLabel + ' ' + attrs.onclick).toLowerCase();
                                                            if (text.includes('登录') || text.includes('login') || text.includes('signin') || text.includes('sign in') || 
                                                                text.includes('提交') || text.includes('submit') || text.includes('确认') || text.includes('confirm') || 
                                                                text.includes('验证') || text.includes('verify') || text.includes('continue') || text.includes('next') || 
                                                                text.includes('save') || text.includes('done')) {
                                                                candidates.push(attrs);
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                return candidates;
                                            """)
                                            
                                            logger.info(f"JavaScript找到 {len(js_result)} 个可能的登录按钮")
                                            for i, candidate in enumerate(js_result):
                                                logger.info(f"JS候选按钮 {i+1}: {candidate}")
                                                if i == 0:  # 使用第一个候选
                                                    login_button = all_clickable_elements[candidate["index"]]
                                                    break
                                        except Exception as e:
                                            logger.info(f"JavaScript查找登录按钮失败: {str(e)}")
                                    
                                    # 如果还是没有找到按钮，尝试使用第一个可见的按钮或链接
                                    if not login_button:
                                        logger.info("使用所有方法都未找到登录按钮，尝试使用第一个可见的按钮或链接...")
                                        for element_info in button_details:
                                            if element_info["is_displayed"] and element_info["is_enabled"]:
                                                # 优先选择按钮或链接
                                                if element_info["tag_name"] in ["button", "a", "input"]:
                                                    logger.info(f"使用第一个可见的按钮或链接: {element_info}")
                                                    login_button = all_clickable_elements[element_info["index"]]
                                                    break
                                        
                                        # 如果没有找到按钮或链接，使用第一个可见的可点击元素
                                        if not login_button:
                                            for element_info in button_details:
                                                if element_info["is_displayed"]:
                                                    logger.info(f"使用第一个可见的可点击元素: {element_info}")
                                                    login_button = all_clickable_elements[element_info["index"]]
                                                    break
                                    
                                    if login_button:
                                        try:
                                            logger.info(f"点击登录按钮: {login_button.tag_name}, 文本: {login_button.text}")
                                            # 使用JavaScript点击，避免元素被遮挡的问题
                                            self.driver.execute_script("arguments[0].click();", login_button)
                                            logger.info("点击登录按钮成功")
                                            
                                            # 增加等待时间，让页面有足够时间加载
                                            time.sleep(5)
                                            
                                            # 检查是否登录成功
                                            current_url = self.driver.current_url
                                            logger.info(f"点击登录按钮后的当前URL: {current_url}")
                                            
                                            # 检查是否在API密钥页面或登录成功页面
                                            if "api_keys" in current_url or "dashboard" in current_url or "profile" in current_url:
                                                logger.info("登录成功，已进入API密钥页面或用户中心")
                                                self.logged_in = True
                                                self.api_key = api_key  # 保存API密钥
                                                
                                                # 尝试访问聊天页面
                                                try:
                                                    logger.info("尝试访问聊天页面...")
                                                    self.driver.get("https://platform.deepseek.com/chat")
                                                    time.sleep(3)
                                                    
                                                    # 检查是否成功访问聊天页面
                                                    chat_url = self.driver.current_url
                                                    logger.info(f"访问聊天页面后的当前URL: {chat_url}")
                                                    
                                                    if "chat" in chat_url.lower():
                                                        logger.info("成功访问聊天页面")
                                                        return {
                                                            "success": True,
                                                            "message": "API密钥认证成功"
                                                        }
                                                    else:
                                                        logger.info("访问聊天页面失败，但已成功登录")
                                                        return {
                                                            "success": True,
                                                            "message": "API密钥认证成功，但无法访问聊天页面"
                                                        }
                                                except Exception as e:
                                                    logger.info(f"访问聊天页面时出错: {str(e)}")
                                                    return {
                                                        "success": True,
                                                        "message": "API密钥认证成功，但无法访问聊天页面"
                                                    }
                                            
                                            # 检查是否有登录成功的标志
                                            try:
                                                # 检查是否有用户菜单、头像或其他登录成功的标志
                                                success_indicators = [
                                                    ".user-menu",
                                                    ".user-avatar",
                                                    ".user-profile",
                                                    ".user-info",
                                                    "[data-testid='user-menu']",
                                                    "[data-testid='user-avatar']",
                                                    ".header-user",
                                                    ".account-menu",
                                                    ".logout-button",
                                                    "button:contains('登出')",
                                                    "button:contains('Logout')",
                                                    "button:contains('Sign out')",
                                                    "a:contains('登出')",
                                                    "a:contains('Logout')",
                                                    "a:contains('Sign out')"
                                                ]
                                                
                                                for indicator in success_indicators:
                                                    try:
                                                        if ":contains" in indicator:
                                                            text = indicator.split(":contains('")[1].split("')")[0]
                                                            xpath = f"//a[contains(text(), '{text}')]"
                                                            element = self.driver.find_element(By.XPATH, xpath)
                                                        else:
                                                            element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                                                        
                                                        if element.is_displayed():
                                                            logger.info(f"发现登录成功标志: {indicator}")
                                                            self.logged_in = True
                                                            self.api_key = api_key  # 保存API密钥
                                                            
                                                            # 尝试访问聊天页面
                                                            try:
                                                                logger.info("尝试访问聊天页面...")
                                                                self.driver.get("https://platform.deepseek.com/chat")
                                                                time.sleep(3)
                                                                
                                                                # 检查是否成功访问聊天页面
                                                                chat_url = self.driver.current_url
                                                                logger.info(f"访问聊天页面后的当前URL: {chat_url}")
                                                                
                                                                if "chat" in chat_url.lower():
                                                                    logger.info("成功访问聊天页面")
                                                                    return {
                                                                        "success": True,
                                                                        "message": "API密钥认证成功"
                                                                    }
                                                                else:
                                                                    logger.info("访问聊天页面失败，但已成功登录")
                                                                    return {
                                                                        "success": True,
                                                                        "message": "API密钥认证成功，但无法访问聊天页面"
                                                                    }
                                                            except Exception as e:
                                                                logger.info(f"访问聊天页面时出错: {str(e)}")
                                                                return {
                                                                    "success": True,
                                                                    "message": "API密钥认证成功，但无法访问聊天页面"
                                                                }
                                                    except NoSuchElementException:
                                                        continue
                                                    
                                                # 检查是否有API密钥相关的元素
                                                api_key_indicators = [
                                                    ".api-key",
                                                    ".api-keys",
                                                    "[data-testid='api-key']",
                                                    "[data-testid='api-keys']",
                                                    "h1:contains('API')",
                                                    "h2:contains('API')",
                                                    "h1:contains('密钥')",
                                                    "h2:contains('密钥')",
                                                    "h1:contains('Key')",
                                                    "h2:contains('Key')",
                                                    ".api-key-list",
                                                    ".key-list",
                                                    ".api-section"
                                                ]
                                                
                                                for indicator in api_key_indicators:
                                                    try:
                                                        if ":contains" in indicator:
                                                            text = indicator.split(":contains('")[1].split("')")[0]
                                                            xpath = f"//h1[contains(text(), '{text}')] | //h2[contains(text(), '{text}')]"
                                                            element = self.driver.find_element(By.XPATH, xpath)
                                                        else:
                                                            element = self.driver.find_element(By.CSS_SELECTOR, indicator)
                                                        
                                                        if element.is_displayed():
                                                            logger.info(f"发现API密钥页面标志: {indicator}")
                                                            self.logged_in = True
                                                            self.api_key = api_key  # 保存API密钥
                                                            
                                                            # 尝试访问聊天页面
                                                            try:
                                                                logger.info("尝试访问聊天页面...")
                                                                self.driver.get("https://platform.deepseek.com/chat")
                                                                time.sleep(3)
                                                                
                                                                # 检查是否成功访问聊天页面
                                                                chat_url = self.driver.current_url
                                                                logger.info(f"访问聊天页面后的当前URL: {chat_url}")
                                                                
                                                                if "chat" in chat_url.lower():
                                                                    logger.info("成功访问聊天页面")
                                                                    return {
                                                                        "success": True,
                                                                        "message": "API密钥认证成功"
                                                                    }
                                                                else:
                                                                    logger.info("访问聊天页面失败，但已成功登录")
                                                                    return {
                                                                        "success": True,
                                                                        "message": "API密钥认证成功，但无法访问聊天页面"
                                                                    }
                                                            except Exception as e:
                                                                logger.info(f"访问聊天页面时出错: {str(e)}")
                                                                return {
                                                                    "success": True,
                                                                    "message": "API密钥认证成功，但无法访问聊天页面"
                                                                }
                                                    except NoSuchElementException:
                                                        continue
                                                        
                                                # 如果没有找到明确的成功标志，尝试直接访问API密钥页面
                                                logger.info("未找到明确的登录成功标志，尝试直接访问API密钥页面...")
                                                try:
                                                    self.driver.get("https://platform.deepseek.com/api_keys")
                                                    time.sleep(3)
                                                    
                                                    api_keys_url = self.driver.current_url
                                                    logger.info(f"访问API密钥页面后的当前URL: {api_keys_url}")
                                                    
                                                    # 如果成功访问API密钥页面，认为登录成功
                                                    if "api_keys" in api_keys_url:
                                                        logger.info("成功访问API密钥页面，登录成功")
                                                        self.logged_in = True
                                                        self.api_key = api_key  # 保存API密钥
                                                        
                                                        # 尝试访问聊天页面
                                                        try:
                                                            logger.info("尝试访问聊天页面...")
                                                            self.driver.get("https://platform.deepseek.com/chat")
                                                            time.sleep(3)
                                                            
                                                            # 检查是否成功访问聊天页面
                                                            chat_url = self.driver.current_url
                                                            logger.info(f"访问聊天页面后的当前URL: {chat_url}")
                                                            
                                                            if "chat" in chat_url.lower():
                                                                logger.info("成功访问聊天页面")
                                                                return {
                                                                    "success": True,
                                                                    "message": "API密钥认证成功"
                                                                }
                                                            else:
                                                                logger.info("访问聊天页面失败，但已成功登录")
                                                                return {
                                                                    "success": True,
                                                                    "message": "API密钥认证成功，但无法访问聊天页面"
                                                                }
                                                        except Exception as e:
                                                            logger.info(f"访问聊天页面时出错: {str(e)}")
                                                            return {
                                                                "success": True,
                                                                "message": "API密钥认证成功，但无法访问聊天页面"
                                                            }
                                                    else:
                                                        logger.info("访问API密钥页面失败，可能需要重新登录")
                                                except Exception as e:
                                                    logger.error(f"访问API密钥页面时出错: {str(e)}")
                                                    logger.info("访问API密钥页面失败，可能需要重新登录")
                                                    
                                                # 如果没有找到明确的成功标志，但URL已改变，也认为可能登录成功
                                                try:
                                                    if current_url != "https://platform.deepseek.com/sign_in":
                                                        logger.info("URL已改变，可能登录成功")
                                                        self.logged_in = True
                                                        self.api_key = api_key  # 保存API密钥
                                                        
                                                        # 尝试访问聊天页面
                                                        try:
                                                            logger.info("尝试访问聊天页面...")
                                                            self.driver.get("https://platform.deepseek.com/chat")
                                                            time.sleep(3)
                                                            
                                                            # 检查是否成功访问聊天页面
                                                            chat_url = self.driver.current_url
                                                            logger.info(f"访问聊天页面后的当前URL: {chat_url}")
                                                            
                                                            if "chat" in chat_url.lower():
                                                                logger.info("成功访问聊天页面")
                                                                return {
                                                                    "success": True,
                                                                    "message": "API密钥认证成功"
                                                                }
                                                            else:
                                                                logger.info("访问聊天页面失败，但已成功登录")
                                                                return {
                                                                    "success": True,
                                                                    "message": "API密钥认证成功，但无法访问聊天页面"
                                                                }
                                                        except Exception as e:
                                                            logger.info(f"访问聊天页面时出错: {str(e)}")
                                                            return {
                                                                "success": True,
                                                                "message": "API密钥认证成功，但无法访问聊天页面"
                                                            }
                                                    
                                                    # 如果所有方法都尝试过仍未确认登录成功，返回失败
                                                    logger.error("无法确认登录状态，API密钥认证失败")
                                                    return {
                                                        "success": False,
                                                        "message": "无法确认登录状态，API密钥认证失败"
                                                    }
                                                    
                                                except Exception as e:
                                                    logger.error(f"检查登录状态时出错: {str(e)}")
                                                    return {
                                                        "success": False,
                                                        "message": f"检查登录状态时出错: {str(e)}"
                                                    }
                                            except Exception as e:
                                                logger.error(f"处理登录流程时出错: {str(e)}")
                                        except Exception as e:
                                            logger.error(f"查找登录元素时出错: {str(e)}")
                            except Exception as e:
                                logger.error(f"使用API密钥登录时出错: {str(e)}")
                    except Exception as e:
                        logger.warning(f"尝试直接访问聊天页面时出错: {e}")
                        # 由于无法确认认证状态，关闭WebDriver并返回错误
                        self.close()
                        return {
                            "success": False,
                            "error": f"未找到API密钥输入框，且尝试直接访问聊天页面失败: {e}"
                        }
            except Exception as e:
                logger.warning(f"设置API密钥时出现问题: {e}")
                # 由于无法设置API密钥，关闭WebDriver并返回错误
                self.close()
                return {
                    "success": False,
                    "error": f"设置API密钥时出现问题: {e}"
                }
            
            # 检查是否成功访问聊天页面
            try:
                current_url = self.driver.current_url
                if "chat" in current_url.lower():
                    self.logged_in = True
                    self.api_key = api_key  # 保存API密钥
                    logger.info("使用API密钥成功访问DeepSeek聊天页面")
                    return {
                        "success": True,
                        "message": "API密钥认证成功"
                    }
                else:
                    # 认证失败时关闭WebDriver
                    self.close()
                    return {
                        "success": False,
                        "error": "无法访问DeepSeek聊天页面，请检查API密钥是否有效"
                    }
            except Exception as e:
                # 如果无法获取当前URL，说明WebDriver可能已关闭
                logger.warning(f"无法获取当前URL: {e}")
                self.close()
                return {
                    "success": False,
                    "error": "无法获取当前页面URL，认证失败"
                }
                
        except TimeoutException:
            logger.error("页面加载超时")
            # 超时时关闭WebDriver
            self.close()
            return {
                "success": False,
                "error": "页面加载超时，请检查网络连接"
            }
        except Exception as e:
            # 确保错误信息是字符串格式
            if isinstance(e, dict):
                error_message = json.dumps(e, ensure_ascii=False)
            else:
                error_message = str(e)
            
            self._log_error_with_screenshot(f"API密钥认证失败: {error_message}", "api_key_auth_error")
            # 异常时关闭WebDriver
            self.close()
            return {
                "success": False,
                "error": f"API密钥认证失败: {error_message}"
            }

    def correct_subtitle_via_web(self, subtitle_text: str, original_text: str, prompt: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        通过DeepSeek网页界面进行字幕校正

        Args:
            subtitle_text: 待校正的字幕文本
            original_text: 原文参考文本
            prompt: 提示词
            api_key: DeepSeek API密钥，如果提供则使用API密钥认证

        Returns:
            Dict[str, Any]: 校正结果
        """
        try:
            # 检查WebDriver是否已初始化
            if not self.driver:
                logger.info("WebDriver未初始化，正在初始化...")
                self._setup_driver()
            
            # 如果提供了API密钥且尚未登录，则使用API密钥进行认证
            if api_key and not self.logged_in:
                logger.info("使用API密钥进行认证...")
                auth_result = self.login_with_api_key(api_key)
                if not auth_result["success"]:
                    # 注意：login_with_api_key方法在失败时已经关闭了WebDriver并重置状态
                    # 直接返回认证失败结果，不再继续执行
                    return auth_result
                # 认证成功，确保logged_in状态正确设置
                self.logged_in = True
            
            # 检查是否已登录
            if not self.logged_in:
                return {
                    "success": False,
                    "error": "尚未登录DeepSeek，请先登录或提供API密钥"
                }
            
            # 确保WebDriver仍然可用
            try:
                # 尝试获取当前URL来验证WebDriver是否仍然可用
                current_url = self.driver.current_url
                logger.info(f"当前页面URL: {current_url}")
            except Exception as e:
                logger.error(f"WebDriver不可用: {e}")
                # 尝试重新初始化WebDriver
                try:
                    self._setup_driver()
                    # 如果提供了API密钥，重新认证
                    if api_key:
                        auth_result = self.login_with_api_key(api_key)
                        if not auth_result["success"]:
                            # 认证失败，login_with_api_key已关闭WebDriver并重置状态
                            return auth_result
                        # 认证成功，确保logged_in状态正确设置
                        self.logged_in = True
                    else:
                        # 如果没有API密钥，无法重新认证
                        return {
                            "success": False,
                            "error": "WebDriver不可用且无API密钥进行重新认证"
                        }
                except Exception as setup_e:
                    logger.error(f"重新初始化WebDriver失败: {setup_e}")
                    return {
                        "success": False,
                        "error": f"WebDriver不可用且无法重新初始化: {setup_e}"
                    }
            
            # 访问DeepSeek聊天页面
            logger.info("正在访问DeepSeek聊天页面...")
            self.driver.get("https://platform.deepseek.com/chat")
            
            # 等待页面加载
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(3)  # 额外等待确保页面完全加载
            
            # 构建完整的输入文本
            full_input_text = f"{prompt}\n\n第一段字幕文本（待校对）：\n{subtitle_text}\n\n第二段原文文本（校对基准）：\n{original_text}"
            
            # 查找输入框
            try:
                input_selectors = [
                    "textarea[placeholder*='请输入']",
                    "textarea[placeholder*='输入']",
                    "textarea[placeholder*='message']",
                    "textarea[placeholder*='Message']",
                    "textarea[placeholder*='请说']",
                    "textarea[placeholder*='Type']",
                    "textarea[placeholder*='type']",
                    "textarea[aria-label*='输入']",
                    "textarea[aria-label*='message']",
                    "textarea[aria-label*='Message']",
                    "textarea[aria-label*='请输入']",
                    "textarea[aria-label*='请说']",
                    "textarea[aria-label*='Type']",
                    "textarea[aria-label*='type']",
                    ".chat-input textarea",
                    ".message-input textarea",
                    ".input-area textarea",
                    ".chat-textarea",
                    ".message-textarea",
                    ".input-textarea",
                    ".chat-input",
                    "#chat-input",
                    "#message-input",
                    "div[contenteditable='true']",
                    "div[role='textbox']",
                    "textarea.form-control",
                    "textarea.chat-input",
                    "textarea.message-input",
                    "textarea.input-area",
                    "textarea",
                    "input[type='text']",
                    "input[type='search']",
                    ".ProseMirror",
                    ".public-DraftEditor-content",
                    ".ql-editor",
                    ".cm-content",
                    ".editor-content",
                    ".chat-editor",
                    ".message-editor",
                    ".input-editor"
                ]
                
                input_element = None
                for selector in input_selectors:
                    try:
                        input_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not input_element:
                    # 尝试通过XPath查找
                    xpath_selectors = [
                        "//textarea[contains(@placeholder, '输入') or contains(@placeholder, 'message') or contains(@placeholder, 'Message') or contains(@placeholder, '请输入') or contains(@placeholder, '请说') or contains(@placeholder, 'Type') or contains(@placeholder, 'type')]",
                        "//textarea[contains(@aria-label, '输入') or contains(@aria-label, 'message') or contains(@aria-label, 'Message') or contains(@aria-label, '请输入') or contains(@aria-label, '请说') or contains(@aria-label, 'Type') or contains(@aria-label, 'type')]",
                        "//div[@contenteditable='true']",
                        "//div[@role='textbox']",
                        "//textarea[contains(@class, 'chat') or contains(@class, 'message') or contains(@class, 'input')]",
                        "//input[@type='text' or @type='search']",
                        "//*[contains(@class, 'ProseMirror') or contains(@class, 'public-DraftEditor-content') or contains(@class, 'ql-editor') or contains(@class, 'cm-content')]",
                        "//*[contains(@class, 'editor') and (contains(@class, 'chat') or contains(@class, 'message') or contains(@class, 'input'))]"
                    ]
                    
                    for xpath in xpath_selectors:
                        try:
                            input_element = self.driver.find_element(By.XPATH, xpath)
                            break
                        except NoSuchElementException:
                            continue
                
                # 输入文本
                input_element.clear()
                input_element.send_keys(full_input_text)
                logger.info("文本输入成功")
                
            except NoSuchElementException as e:
                logger.error(f"找不到输入框: {e}")
                return {
                    "success": False,
                    "error": "找不到输入框，可能是页面结构已更改"
                }
            
            # 查找并点击提交按钮
            try:
                submit_button_selectors = [
                    "button[type='submit']",
                    "button.send-btn",
                    "button.submit-btn",
                    "button.chat-send",
                    "button.message-send",
                    "button:contains('发送')",
                    "button:contains('提交')",
                    "button:contains('Send')",
                    "button:contains('Submit')",
                    "button[aria-label*='发送']",
                    "button[aria-label*='提交']",
                    "button[aria-label*='Send']",
                    "button[aria-label*='Submit']",
                    ".send-button",
                    ".submit-button",
                    ".chat-button",
                    ".message-button",
                    "#send-button",
                    "#submit-button",
                    "#chat-button",
                    "#message-button",
                    "button.btn-primary",
                    "button.btn-send",
                    "button.btn-submit",
                    ".btn-primary",
                    ".btn-send",
                    ".btn-submit",
                    "svg.send-icon",
                    "svg.submit-icon",
                    ".icon-send",
                    ".icon-submit",
                    "button svg",
                    ".button svg"
                ]
                
                submit_button = None
                for selector in submit_button_selectors:
                    try:
                        if ":contains(" in selector:
                            # 使用XPath查找包含特定文本的按钮
                            text = selector.split("'")[1]
                            submit_button = self.driver.find_element(By.XPATH, f"//button[contains(text(), '{text}')]")
                        else:
                            submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if not submit_button:
                    # 尝试通过XPath查找
                    xpath_selectors = [
                        "//button[contains(text(), '发送') or contains(text(), '提交') or contains(text(), 'Send') or contains(text(), 'Submit')]",
                        "//button[contains(@aria-label, '发送') or contains(@aria-label, '提交') or contains(@aria-label, 'Send') or contains(@aria-label, 'Submit')]",
                        "//button[contains(@class, 'send') or contains(@class, 'submit') or contains(@class, 'chat') or contains(@class, 'message')]",
                        "//button[@type='submit']",
                        "//button[contains(@class, 'btn-primary') or contains(@class, 'btn-send') or contains(@class, 'btn-submit')]",
                        "//button[.//svg[contains(@class, 'send') or contains(@class, 'submit')]]",
                        "//button[.//*[contains(@class, 'icon') and (contains(@class, 'send') or contains(@class, 'submit'))]]",
                        "//*[contains(@class, 'send-button') or contains(@class, 'submit-button') or contains(@class, 'chat-button') or contains(@class, 'message-button')]"
                    ]
                    
                    for xpath in xpath_selectors:
                        try:
                            submit_button = self.driver.find_element(By.XPATH, xpath)
                            break
                        except NoSuchElementException:
                            continue
                
                submit_button.click()
                logger.info("提交按钮点击成功")
                
            except NoSuchElementException as e:
                logger.error(f"找不到提交按钮: {e}")
                return {
                    "success": False,
                    "error": "找不到提交按钮，可能是页面结构已更改"
                }
            
            # 等待响应
            logger.info("等待DeepSeek响应...")
            time.sleep(10)  # 初始等待
            
            # 尝试获取响应结果
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    logger.info(f"尝试获取响应结果 (第{attempt+1}次)...")
                    
                    # 等待响应出现
                    response_selectors = [
                        ".response-content",
                        ".message-response",
                        ".chat-response",
                        ".ai-response",
                        ".response-text",
                        ".message-content",
                        ".bot-response",
                        ".assistant-response",
                        ".deepseek-response",
                        ".message-text",
                        ".chat-text",
                        ".ai-text",
                        ".bot-text",
                        ".assistant-text",
                        ".deepseek-text",
                        ".prose",
                        ".markdown",
                        ".content",
                        ".text",
                        ".output",
                        ".result",
                        ".answer",
                        ".reply"
                    ]
                    
                    response_element = None
                    for selector in response_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                # 获取最后一个元素（最新的响应）
                                response_element = elements[-1]
                                logger.info(f"通过选择器 '{selector}' 找到响应元素")
                                break
                        except NoSuchElementException:
                            continue
                    
                    if not response_element:
                        # 尝试通过XPath查找响应元素
                        xpath_selectors = [
                            "//div[contains(@class, 'response') or contains(@class, 'message') or contains(@class, 'chat')]",
                            "//*[contains(@class, 'message') and contains(@class, 'content')]",
                            "//*[contains(@class, 'response') and contains(@class, 'content')]",
                            "//*[contains(@class, 'ai') and contains(@class, 'response')]",
                            "//*[contains(@class, 'bot') and contains(@class, 'response')]",
                            "//*[contains(@class, 'assistant') and contains(@class, 'response')]",
                            "//*[contains(@class, 'deepseek') and contains(@class, 'response')]",
                            "//*[contains(@class, 'prose')]",
                            "//*[contains(@class, 'markdown')]",
                            "//*[contains(@class, 'content') and not(contains(@class, 'input'))]",
                            "//*[contains(@class, 'text') and not(contains(@class, 'input'))]",
                            "//*[contains(@class, 'output')]",
                            "//*[contains(@class, 'result')]",
                            "//*[contains(@class, 'answer')]",
                            "//*[contains(@class, 'reply')]"
                        ]
                        
                        for xpath in xpath_selectors:
                            try:
                                elements = self.driver.find_elements(By.XPATH, xpath)
                                if elements:
                                    # 获取最后一个元素（最新的响应）
                                    response_element = elements[-1]
                                    logger.info(f"通过XPath '{xpath}' 找到响应元素")
                                    break
                            except NoSuchElementException:
                                continue
                    
                    if not response_element:
                        logger.warning("无法通过常规方式定位响应元素，尝试获取最后一条消息")
                        # 尝试获取最后一条消息
                        messages = self.driver.find_elements(By.CSS_SELECTOR, ".message, .chat-message")
                        if messages:
                            response_element = messages[-1]
                            logger.info("通过获取最后一条消息找到响应元素")
                    
                    if response_element:
                        corrected_text = response_element.text
                        if corrected_text.strip():
                            logger.info("成功获取DeepSeek响应")
                            return {
                                "success": True,
                                "corrected_subtitle": corrected_text,
                                "original_subtitle": subtitle_text,
                                "reference_text": original_text,
                                "processing_time": 10 + attempt * 5,  # 估计的处理时间
                                "model_used": "deepseek-web-interface"
                            }
                        else:
                            logger.warning(f"响应元素为空 (第{attempt+1}次尝试)")
                            if attempt < max_attempts - 1:
                                time.sleep(5)  # 等待更长时间
                                continue
                    else:
                        logger.warning(f"无法找到响应元素 (第{attempt+1}次尝试)")
                        if attempt < max_attempts - 1:
                            time.sleep(5)  # 等待更长时间
                            continue
                    
                except Exception as e:
                    logger.error(f"获取响应时发生错误 (第{attempt+1}次尝试): {str(e)}")
                    if attempt < max_attempts - 1:
                        time.sleep(5)  # 等待更长时间
                        continue
            
            # 所有尝试都失败
            self._log_error_with_screenshot("无法获取DeepSeek响应，所有尝试都失败", "response_error")
            return {
                "success": False,
                "error": "无法获取DeepSeek响应，可能是响应尚未生成或页面结构已更改"
            }
                
        except Exception as e:
            # 确保错误信息是字符串格式
            if isinstance(e, dict):
                error_message = json.dumps(e, ensure_ascii=False)
            else:
                error_message = str(e)
            
            self._log_error_with_screenshot(f"字幕校正失败: {error_message}", "correction_error")
            
            # 如果错误是由于WebDriver问题导致的，确保关闭WebDriver并重置状态
            if "WebDriver" in error_message or "driver" in error_message.lower():
                logger.info("检测到WebDriver相关错误，关闭WebDriver并重置状态")
                self.close()
            
            return {
                "success": False,
                "error": f"字幕校正失败: {error_message}",
                "original_subtitle": subtitle_text,
                "reference_text": original_text
            }
    
    def close(self):
        """关闭WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False
            self.api_key = None  # 重置API密钥
            logger.info("WebDriver已关闭，登录状态已重置")

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器"""
        self.close()


def get_web_interface_client(headless: bool = True, chrome_driver_path: Optional[str] = None) -> DeepSeekWebInterface:
    """
    获取DeepSeek网页交互客户端

    Args:
        headless: 是否使用无头模式（不显示浏览器界面）
        chrome_driver_path: ChromeDriver路径，如果不提供则自动查找

    Returns:
        DeepSeekWebInterface: 网页交互客户端实例
    """
    return DeepSeekWebInterface(headless=headless, chrome_driver_path=chrome_driver_path)