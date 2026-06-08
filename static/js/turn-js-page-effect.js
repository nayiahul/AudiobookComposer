/**
 * Turn.js翻页效果
 * 基于翻页效果.html的实现
 */

// 使用统一的日志过滤机制，不重复重写console.log
// 如果app.js已经重写了console.log，则不再重写
if (typeof console.logFilter !== 'function') {
    // 只在app.js未设置日志过滤时才设置
    const originalConsoleLogPage = console.log;
    console.log = function(...args) {
        // 只允许错误级别的日志输出
        if (args.length > 0 && typeof args[0] === 'string' && args[0].includes('错误')) {
            originalConsoleLogPage.apply(console, args);
        }
    };
}

class TurnJsPageEffect {
    /**
     * 构造函数
     * @param {HTMLElement|string} canvas - 画布元素或ID
     * @param {Object} options - 配置选项
     */
    constructor(canvas, options = {}) {
        this.canvas = typeof canvas === 'string' ? document.getElementById(canvas) : canvas;
        this.options = Object.assign({
            width: this.canvas ? this.canvas.width : 800,
            height: this.canvas ? this.canvas.height : 600,
            display: 'double',
            acceleration: true,
            elevation: 50,
            gradients: true,
            autoCenter: true,
            when: {
                start: function() {},
                turning: function(e, page, view) {},
                turned: function(e, page, view) {}
            }
        }, options);
        
        this.magazine = null;
        this.pages = null;
        this.content = null;
        this.contentText = null;
        this.alert = null;
        this.moveObj = null;
        this.endObj = null;
        this.timer = null;
        this.originalContent = '';
        this.initialized = false;
    }

    /**
     * 初始化Turn.js翻页效果
     * @returns {Promise} - 返回一个Promise，表示初始化完成
     */
    async init() {
        return new Promise((resolve, reject) => {
            try {
                // 保存原始内容
                this.originalContent = this.canvas.innerHTML;
                
                // 创建翻页结构
                this.createTurnJsStructure();
                
                // 初始化Turn.js
                this.initTurnJs();
                
                // 添加触摸和鼠标事件
                this.addTouchEvents();
                
                this.initialized = true;
                resolve();
            } catch (error) {
                console.error('初始化Turn.js翻页效果失败:', error);
                reject(error);
            }
        });
    }

    /**
     * 创建Turn.js翻页结构
     */
    createTurnJsStructure() {
        // 清空画布
        this.canvas.innerHTML = '';
        
        // 创建翻页结构
        const magazine = document.createElement('div');
        magazine.id = 'turn-js-magazine';
        magazine.style.width = '100%';
        magazine.style.height = '100%';
        magazine.style.position = 'relative';
        magazine.style.overflow = 'hidden';
        
        const pages = document.createElement('div');
        pages.id = 'turn-js-pages';
        pages.style.width = '100%';
        pages.style.height = '100%';
        pages.style.position = 'relative';
        pages.style.zIndex = '1';
        
        const content = document.createElement('div');
        content.id = 'turn-js-content';
        content.style.height = '0';
        content.style.overflow = 'hidden';
        content.style.width = '100%';
        
        const contentText = document.createElement('div');
        contentText.id = 'turn-js-content-text';
        contentText.style.width = '100%';
        contentText.style.whiteSpace = 'pre-wrap';
        contentText.style.boxSizing = 'border-box';
        contentText.style.padding = '0 10px';
        contentText.innerHTML = this.originalContent || '<div style="padding: 20px; text-align: center;">第1页内容</div><div style="padding: 20px; text-align: center;">第2页内容</div><div style="padding: 20px; text-align: center;">第3页内容</div><div style="padding: 20px; text-align: center;">第4页内容</div>';
        
        const alert = document.createElement('div');
        alert.id = 'turn-js-alert';
        alert.style.position = 'absolute';
        alert.style.bottom = '40px';
        alert.style.left = '50%';
        alert.style.transform = 'translateX(-50%)';
        alert.style.background = 'rgba(0,0,0,0.6)';
        alert.style.borderRadius = '4px';
        alert.style.color = '#fff';
        alert.style.zIndex = '10';
        alert.style.fontSize = '12px';
        alert.style.padding = '6px 10px';
        alert.style.display = 'none';
        
        content.appendChild(contentText);
        magazine.appendChild(pages);
        magazine.appendChild(content);
        this.canvas.appendChild(magazine);
        this.canvas.appendChild(alert);
        
        // 保存引用
        this.magazine = magazine;
        this.pages = pages;
        this.content = content;
        this.contentText = contentText;
        this.alert = alert;
    }

    /**
     * 初始化Turn.js
     */
    initTurnJs() {
        const $wrap = $(this.magazine);
        const $page = $(this.pages);
        const $content = $(this.contentText);
        
        const w = this.options.width; // 窗口的宽度
        const h = this.options.height; // 窗口的高度
        
        const writeStr = $content.html();
        const len = writeStr.length; // 总长度
        const cH = $content.height(); // 总高度
        let pageStrNum; // 每页大概有多少个字符
        
        // 清空页面
        $page.empty();
        
        if (cH > h) {
            pageStrNum = (h / cH) * len; // 每页大概有多少个字符
            let obj = this.overflowhiddenTow($content, writeStr, h);
            $page.append('<div class="turn-page" style="width:' + w + 'px;height:' + h + 'px;background:#fff;">' + obj.curr + '</div>');
            
            while (obj.next && obj.next.length > 0) {
                obj = this.overflowhiddenTow($content, obj.next, h);
                $page.append('<div class="turn-page" style="width:' + w + 'px;height:' + h + 'px;background:#fff;">' + obj.curr + '</div>');
            }
        } else {
            // 如果内容不足一页，创建示例页面
            $page.append('<div class="turn-page" style="width:' + w + 'px;height:' + h + 'px;background:#fff;"><div style="padding: 20px; text-align: center;">第1页内容</div></div>');
            $page.append('<div class="turn-page" style="width:' + w + 'px;height:' + h + 'px;background:#fff;"><div style="padding: 20px; text-align: center;">第2页内容</div></div>');
        }
        
        // 初始化Turn.js
        $page.turn({
            width: w,
            height: h,
            elevation: this.options.elevation,
            display: this.options.display,
            gradients: this.options.gradients,
            autoCenter: this.options.autoCenter,
            acceleration: this.options.acceleration,
            when: this.options.when
        });
    }

    /**
     * 文字切割算法
     * @param {jQuery} $texts - jQuery对象
     * @param {string} str - 文本内容
     * @param {number} at - 高度限制
     * @returns {Object} - 切割结果
     */
    overflowhiddenTow($texts, str, at) {
        const pageStrNum = (at / $texts.height()) * str.length;
        let throat = pageStrNum;
        let tempstr = str.substring(0, throat);
        const len = str.length;
        
        $texts.html(tempstr);
        
        // 取的字节较少,应该增加
        while ($texts.height() < at && throat < len) {
            throat = throat + 2;
            tempstr = str.substring(0, throat);
            $texts.html(tempstr);
        }
        
        // 取的字节较多,应该减少
        while ($texts.height() > at && throat > 0) {
            throat = throat - 2;
            tempstr = str.substring(0, throat);
            $texts.html(tempstr);
        }
        
        return {
            curr: str.substring(0, throat),
            next: str.substring(throat)
        };
    }

    /**
     * 添加触摸和鼠标事件
     */
    addTouchEvents() {
        const $wrap = $(this.magazine);
        const $page = $(this.pages);
        const $alert = $(this.alert);
        
        // 获取触摸或鼠标位置
        const getPoint = (e) => {
            let obj = e;
            if (e.targetTouches && e.targetTouches.length > 0) {
                obj = e.targetTouches[0];
            }
            return obj;
        };
        
        // 触摸/鼠标开始事件
        $wrap.on("touchstart mousedown", (e) => {
            const obj = getPoint(e);
            this.moveObj = {
                x: obj.clientX
            };
        });
        
        // 触摸/鼠标移动事件
        $wrap.on("touchmove mousemove", (e) => {
            const obj = getPoint(e);
            this.endObj = {
                x: obj.clientX
            };
        });
        
        // 触摸/鼠标结束事件
        $wrap.on("touchend mouseup", (e) => {
            if (this.moveObj && this.endObj) {
                const mis = this.endObj.x - this.moveObj.x;
                if (Math.abs(mis) > 30) {
                    const pageCount = $page.turn("pages"); // 总页数
                    const currentPage = $page.turn("page"); // 当前页
                    
                    if (mis > 0) {
                            // 向右滑动，上一页
                            if (currentPage > 1) {
                                $page.turn('page', currentPage - 1);
                            } else {
                                console.log("错误: 已经是第一页");
                                this.showAlert('已经是第一页');
                            }

                    } else {
                        // 向左滑动，下一页
                        if (currentPage < pageCount) {
                            $page.turn('page', currentPage + 1);
                        } else {
                            console.log("错误: 已经是最后一页");
                            this.showAlert('已经是最后一页');
                        }
                    }
                }
            }
            
            this.moveObj = null;
            this.endObj = null;
        });
        
        // 添加键盘事件
        $(document).on('keydown', (e) => {
            const currentPage = $page.turn("page");
            const pageCount = $page.turn("pages");
            
            if (e.keyCode === 37) { // 左箭头
                if (currentPage > 1) {
                    $page.turn('page', currentPage - 1);
                } else {
                    this.showAlert('已经是第一页');
                }
            } else if (e.keyCode === 39) { // 右箭头
                if (currentPage < pageCount) {
                    $page.turn('page', currentPage + 1);
                } else {
                    this.showAlert('已经是最后一页');
                }
            }
        });
    }

    /**
     * 显示提示信息
     * @param {string} msg - 提示信息
     */
    showAlert(msg) {
        const $alert = $(this.alert);
        clearTimeout(this.timer);
        $alert.text(msg);
        $alert.fadeIn();
        this.timer = setTimeout(() => {
            $alert.fadeOut();
        }, 1000);
    }

    /**
     * 销毁翻页效果
     */
    destroy() {
        if (!this.initialized) {
            return;
        }
        
        // 清除定时器
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
        
        // 移除事件监听
        if (this.magazine) {
            $(this.magazine).off("touchstart mousedown");
            $(this.magazine).off("touchmove mousemove");
            $(this.magazine).off("touchend mouseup");
        }
        
        // 移除键盘事件
        $(document).off('keydown');
        
        // 销毁Turn.js实例
        if (this.pages) {
            $(this.pages).turn('destroy');
        }
        
        // 恢复原始内容
        if (this.canvas && this.originalContent) {
            this.canvas.innerHTML = this.originalContent;
        }
        
        // 清空引用
        this.magazine = null;
        this.pages = null;
        this.content = null;
        this.contentText = null;
        this.alert = null;
        this.moveObj = null;
        this.endObj = null;
        this.initialized = false;
    }
}

// 将类添加到全局作用域
window.TurnJsPageEffect = TurnJsPageEffect;