// PDF to Video Web App JavaScript

// 全局控制开关，将控制台信息输出到处理日志中
const originalConsoleLog = console.log;
const originalConsoleInfo = console.info;
const originalConsoleDebug = console.debug;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

// 添加日志过滤标志，防止其他文件重复重写console.log
console.logFilter = true;

// 全局日志函数，用于将控制台信息输出到处理日志
function logToUI(message, level = 'info') {
    // 延迟执行，确保VideoCreatorApp实例已创建
    setTimeout(() => {
        if (window.videoApp && window.videoApp.addLogEntry) {
            // 确保日志级别正确映射
            let mappedLevel = level;
            if (level === 'log') {
                mappedLevel = 'info';
            }
            window.videoApp.addLogEntry(message, mappedLevel);
        }
    }, 0);
}

console.log = function(...args) {
    // 输出到原始控制台
    originalConsoleLog.apply(console, args);
    
    // 将信息转换为字符串并输出到处理日志
    const message = args.map(arg => {
        if (typeof arg === 'object') {
            try {
                return JSON.stringify(arg);
            } catch (e) {
                return String(arg);
            }
        }
        return String(arg);
    }).join(' ');
    
    logToUI(message, 'info');
};

console.info = function(...args) {
    // 输出到原始控制台
    originalConsoleInfo.apply(console, args);
    
    // 将信息转换为字符串并输出到处理日志
    const message = args.map(arg => {
        if (typeof arg === 'object') {
            try {
                return JSON.stringify(arg);
            } catch (e) {
                return String(arg);
            }
        }
        return String(arg);
    }).join(' ');
    
    logToUI(message, 'info');
};

console.debug = function(...args) {
    // 输出到原始控制台
    originalConsoleDebug.apply(console, args);
    
    // 将信息转换为字符串并输出到处理日志
    const message = args.map(arg => {
        if (typeof arg === 'object') {
            try {
                return JSON.stringify(arg);
            } catch (e) {
                return String(arg);
            }
        }
        return String(arg);
    }).join(' ');
    
    logToUI(message, 'debug');
};

console.warn = function(...args) {
    // 输出到原始控制台
    originalConsoleWarn.apply(console, args);
    
    // 将信息转换为字符串并输出到处理日志
    const message = args.map(arg => {
        if (typeof arg === 'object') {
            try {
                return JSON.stringify(arg);
            } catch (e) {
                return String(arg);
            }
        }
        return String(arg);
    }).join(' ');
    
    logToUI(message, 'warning');
};

console.error = function(...args) {
    // 输出到原始控制台
    originalConsoleError.apply(console, args);
    
    // 将信息转换为字符串并输出到处理日志
    const message = args.map(arg => {
        if (typeof arg === 'object') {
            try {
                return JSON.stringify(arg);
            } catch (e) {
                return String(arg);
            }
        }
        return String(arg);
    }).join(' ');
    
    logToUI(message, 'error');
};

class VideoCreatorApp {
    constructor() {
        this.uploadedFiles = {};
        this.memoryFiles = {}; // 初始化内存文件存储
        this.currentJob = null;
        this.pageCount = 0;
        this.pageTimings = [];
        this.audioDuration = 0;
        
        // 启用界面日志显示，以便显示控制台信息
        this.disableUILogging = false;
        
        // 添加防重复检查标志
        this.isCheckingFiles = false;
        this.configLoaded = false;
        this.hasDeepSeekApiKey = false; // 系统是否已配置DeepSeek API密钥
        
        // 初始化模型状态缓存
        this.modelStatusCache = null;
        this.lastUpdateTime = null;

        this.initializeElements();
        this.setDefaultValues();
        this.bindEvents();
        
        // 初始化竖排双页模式和PDF边界裁剪设置的禁用/启用状态
        this.initializeToggleStates();
        
        // 并行执行初始化任务，提高加载速度
        Promise.all([
            this.checkFFmpegStatus(),
            this.checkAndLoadConfigFile(),
            this.fetchModelStatus().then(() => this.updateModelSelectUI())
        ]).catch(error => {
            console.error('初始化任务执行失败:', error);
        });
        
        // 不再自动加载配置，只在用户点击"加载配置"按钮时加载
        // this.loadPageTimingsData();
        
        // 将实例保存到全局变量，以便全局日志函数可以访问
        window.videoApp = this;
        
        // 初始化WebSocket连接
        this.initializeWebSocket();
        
        // 初始化字幕文件选择器
        this.initializeSubtitleFileSelect();

        // 初始化DeepSeek功能
        this.initializeDeepSeekEvents();
        
        // 初始化字幕校验功能
        this.initializeSubtitleValidation();

        // 初始化时检查是否已经上传了文件，如果是则显示所有section
        this.initializeSectionVisibility();
    }

    // 初始化section可见性
    initializeSectionVisibility() {
        console.log('初始化section可见性...');

        // 检查是否已经上传了必要文件
        if (this.uploadedFiles &&
            (this.uploadedFiles.pdf || this.uploadedFiles.audio || this.uploadedFiles.subs)) {
            console.log('检测到已上传文件，显示所有section');
            this.showNextSection();
        } else {
            console.log('暂无上传文件，section保持隐藏');
        }
        
        // 初始化DeepSeek校正方式选择（Streamlit标签页）
        const defaultStreamlitTab = document.querySelector('.streamlit-tab.active');
        if (defaultStreamlitTab) {
            console.log('默认校正方式:', defaultStreamlitTab.dataset.tab);
            this.toggleCorrectionMethod(defaultStreamlitTab.dataset.tab);
            
            // 添加视觉提示
            const methodDescription = document.getElementById('method-description');
            if (methodDescription) {
                methodDescription.innerHTML = `<i class="bi bi-info-circle me-1"></i>当前校正方式: ${defaultStreamlitTab.dataset.tab} (已初始化)`;
            }
        }
        
        // 确保网页交互模式配置区域可以正确显示
        const webConfigSection = document.getElementById('web-config-section');
        if (webConfigSection) {
            console.log('网页交互配置区域已找到');
            // 添加视觉提示
            webConfigSection.style.border = '2px solid red';
            setTimeout(() => {
                webConfigSection.style.border = '';
            }, 3000);
        } else {
            console.error('网页交互配置区域未找到');
        }
    }

    initializeWebSocket() {
        console.log('正在初始化WebSocket连接...');
        
        // 初始化Socket.IO连接
        this.socket = io();
        
        // 连接成功事件
        this.socket.on('connect', () => {
            console.log('✓ WebSocket已连接到服务器');
            this.addLogEntry('✓ 已连接到服务器日志流', 'success');
            
            // 请求最近的日志
            this.socket.emit('request_logs');
        });
        
        // 连接断开事件
        this.socket.on('disconnect', () => {
            console.log('✗ WebSocket与服务器断开连接');
            this.addLogEntry('✗ 与服务器断开连接', 'warning');
        });
        
        // 接收日志消息
        this.socket.on('log_message', (data) => {
            console.log('收到日志消息:', data);
            if (data && data.message) {
                this.addLogEntry(data.message, data.level ? data.level.toLowerCase() : 'info');
                
                // 如果正在提取字幕，更新状态显示区域
                if (this.isExtractingSubtitle) {
                    const statusDiv = document.getElementById('extract-subtitle-status');
                    if (statusDiv) {
                        const msg = data.message;
                        let badgeClass = 'bg-secondary';
                        let category = '系统';
                        let content = msg;

                        // 根据消息内容分类
                        if (msg.includes('初始化') || msg.includes('加载')) {
                            badgeClass = 'bg-info';
                            category = '初始化';
                        } else if (msg.includes('模型')) {
                            badgeClass = 'bg-primary';
                            category = '模型';
                        } else if (msg.includes('处理') || msg.includes('转写') || msg.includes('分段')) {
                            badgeClass = 'bg-primary';
                            category = '处理';
                        } else if (msg.includes('完成') || msg.includes('成功')) {
                            badgeClass = 'bg-success';
                            category = '完成';
                        } else if (msg.includes('错误') || msg.includes('失败')) {
                            badgeClass = 'bg-danger';
                            category = '错误';
                        } else if (msg.includes('下载')) {
                            badgeClass = 'bg-warning text-dark';
                            category = '下载';
                        }

                        // 截断过长的消息内容
                        if (content.length > 50) {
                            content = content.substring(0, 48) + '...';
                        }
                        
                        // 使用HTML格式显示，包含徽章
                        statusDiv.style.display = 'block';
                        statusDiv.innerHTML = `<div class="d-flex align-items-center"><span class="badge ${badgeClass} me-2">${category}</span><span title="${msg}">${content}</span></div>`;
                    }
                }
            }
        });
        
        // 接收状态消息
        this.socket.on('status', (data) => {
            console.log('收到状态消息:', data);
            if (data && data.msg) {
                this.addLogEntry(data.msg, 'info');
            }
        });
        
        // 连接错误事件
        this.socket.on('connect_error', (error) => {
            console.error('WebSocket连接错误:', error);
            this.addLogEntry('WebSocket连接错误: ' + error.message, 'error');
        });
        
        console.log('WebSocket事件监听器已设置');
    }

    initializeSubtitleFileSelect() {
        // 初始化字幕文件选择器
        this.subtitleFileSelect = document.getElementById('subtitle-file-select');
        
        // 如果字幕文件选择器不存在，创建一个隐藏的选择器
        if (!this.subtitleFileSelect) {
            console.log('字幕文件选择器不存在，创建隐藏的选择器');
            this.subtitleFileSelect = document.createElement('select');
            this.subtitleFileSelect.id = 'subtitle-file-select';
            this.subtitleFileSelect.style.display = 'none';
            document.body.appendChild(this.subtitleFileSelect);
        }
        
        // 添加事件监听器
        this.subtitleFileSelect.addEventListener('change', () => {
            const selectedOption = this.subtitleFileSelect.options[this.subtitleFileSelect.selectedIndex];
            console.log('已选择字幕文件:', selectedOption.value);
            // 可以在这里添加预加载字幕文件的逻辑
            // 或者只是记录用户的选择，等待点击"加载字幕内容"按钮
        });
    }

    initializeElements() {
        // File upload elements
        this.fileInput = document.getElementById('file-input');
        this.uploadStatus = document.getElementById('upload-status');

        // Upload areas
        this.uploadAreas = document.querySelectorAll('.upload-area');
        this.configUploadArea = document.getElementById('config-upload-area');
        this.videoUploadArea = document.getElementById('video-upload-area');
        this.subsUploadArea = document.querySelector('[data-type="subs"]');

        // 字幕处理元素
        this.subtitleSection = document.getElementById('subtitle-section');
        this.whisperModelSelect = document.getElementById('whisper-model-select');
        this.audioLanguageSelect = document.getElementById('audio-language-select');

        this.extractSubtitleBtn = document.getElementById('extract-subtitle-btn');
        this.extractSubtitleStatus = document.getElementById('extract-subtitle-status');
        this.extractStatusText = document.getElementById('extract-status-text');

        // Section elements
        this.uploadSection = document.getElementById('upload-section');
        this.timingSection = document.getElementById('timing-section');
        this.pageTimingSection = document.getElementById('page-timing-section');
        this.deepseekSection = document.getElementById('deepseek-section');
        this.settingsSection = document.getElementById('settings-section');
        this.createSection = document.getElementById('create-section');
        this.progressSection = document.getElementById('progress-section');
        this.resultsSection = document.getElementById('results-section');

        // Timing elements
        this.pageTimingsGrid = document.getElementById('page-timings-grid');
        this.totalDuration = document.getElementById('total-duration');
        this.generateTimingsFromSubsBtn = document.getElementById('generate-timings-from-subs');
        this.verticalLayout = document.getElementById('vertical-layout'); // 竖排布局选项移到翻页点设置区域

        // Settings elements
        this.startPage = document.getElementById('start-page');
        this.endPage = document.getElementById('end-page');
        this.timingStartPage = document.getElementById('timing-start-page');
        this.timingEndPage = document.getElementById('timing-end-page');
        this.quality = document.getElementById('quality');
        this.bitrate = document.getElementById('bitrate');
        this.resolution = document.getElementById('resolution');
        this.transitionEffect = document.getElementById('transition-effect'); // 添加翻页效果选项
        this.outputName = document.getElementById('output-name');
        this.estimatedSize = document.getElementById('estimated-size');

        // Action elements
        this.createVideoBtn = document.getElementById('create-video-btn');
        this.downloadLink = document.getElementById('download-link');
        this.previewVideoBtn = document.getElementById('preview-video-btn');

        // Progress elements
        this.progressBar = document.getElementById('progress-bar');
        this.progressMessage = document.getElementById('progress-message');
        this.progressPercent = document.getElementById('progress-percent');
        this.jobId = document.getElementById('job-id');
        this.startTime = document.getElementById('start-time');

        // Log elements
        this.logSection = document.getElementById('log-section');
        this.logContainer = document.getElementById('log-container');
        this.clearLogBtn = document.getElementById('clear-log-btn');
        this.toggleLogBtn = document.getElementById('toggle-log-btn');
        this.logExpanded = false;

        // Results elements
        this.resultFilename = document.getElementById('result-filename');
        this.resultFilesize = document.getElementById('result-filesize');
        this.resultTime = document.getElementById('result-time');

        // Jobs list - 已移除处理历史功能

        // FFmpeg status
        this.ffmpegStatus = document.getElementById('ffmpeg-status');

        // Preview elements
        this.pdfPreviewModal = document.getElementById('pdfPreviewModal');
        this.pdfPreviewCanvas = document.getElementById('pdf-preview-canvas');
        this.pdfPageInfo = document.getElementById('pdf-page-info');
        this.pdfPageJump = document.getElementById('pdf-page-jump');
        this.pdfPageJumpBtn = document.getElementById('pdf-page-jump-btn');
        this.pdfPrevPageBtn = document.getElementById('pdf-prev-page');
        this.pdfNextPageBtn = document.getElementById('pdf-next-page');
        this.subsPreviewModal = document.getElementById('subsPreviewModal');
        this.subsPreviewTbody = document.getElementById('subs-preview-tbody');
        this.configPreviewModal = document.getElementById('configPreviewModal');
        this.configPreviewContent = document.getElementById('config-preview-content');
        this.videoPreviewModal = document.getElementById('videoPreviewModal');
        this.videoPreviewPlayer = document.getElementById('video-preview-player');
        this.videoPreviewFilename = document.getElementById('video-preview-filename');
        this.videoPreviewFilesize = document.getElementById('video-preview-filesize');
        this.videoPreviewTime = document.getElementById('video-preview-time');
        
        // Audio player elements
        this.audioPlayerContainer = document.getElementById('audio-player-container');
        this.audioPlayer = document.getElementById('audio-player');
        
        // Audio hover player elements - REMOVED
        // this.audioFilenameHover = document.getElementById('audio-file-name');
        // this.audioHoverPlayer = document.getElementById('audio-hover-player');
        // this.audioHoverPlayerElement = document.getElementById('audio-hover-player-element');
        // this.audioPinBtn = document.getElementById('audio-pin-btn');
        // this.audioCloseBtn = document.getElementById('audio-close-btn');
        
        // Audio hover player state - REMOVED
        // this.audioHoverPinned = false;
        // this.audioHoverTimeout = null;
        // this.audioHoverShowTimeout = null;
        
        // PDF hover preview elements - REMOVED
        // this.pdfFilenameHover = document.getElementById('pdf-file-name');
        // this.pdfHoverPreview = document.getElementById('pdf-hover-preview');
        // this.pdfHoverPreviewElement = document.getElementById('pdf-hover-preview-element');
        // this.pdfHoverTimeout = null;
        // this.pdfHoverShowTimeout = null;
        
        // Subtitle hover preview elements - REMOVED
        // this.subsFilenameHover = document.getElementById('subs-file-name');
        // this.subsHoverPreview = document.getElementById('subs-hover-preview');
        // this.subsHoverPreviewElement = document.getElementById('subs-hover-preview-element');
        // this.subsHoverTimeout = null;
        // this.subsHoverShowTimeout = null;
        
        // Config hover preview elements - REMOVED
        // this.configFilenameHover = document.getElementById('config-file-name');
        // this.configHoverPreview = document.getElementById('config-hover-preview');
        // this.configHoverPreviewElement = document.getElementById('config-hover-preview-element');
        // this.configHoverTimeout = null;
        // this.configHoverShowTimeout = null;
        
        // Video hover preview elements - REMOVED
        // this.videoFilenameHover = document.getElementById('video-file-name');
        // this.videoHoverPreview = document.getElementById('video-hover-preview');
        // this.videoHoverPreviewElement = document.getElementById('video-hover-preview-element');
        
        // PDF preview state
        this.currentPdfPage = 1;
        this.pdfDoc = null;
        this.pdfLoading = false; // 添加PDF加载状态标志
        
        // 初始化模型信息显示
        setTimeout(() => {
            this.updateModelInfo();
        }, 500);
        
        // 裁剪设置元素
        this.enableCrop = document.getElementById('enableCrop');
        this.cropSettings = document.getElementById('cropSettings');
        this.oddTopCrop = document.getElementById('oddTopCrop');
        this.oddBottomCrop = document.getElementById('oddBottomCrop');
        this.oddLeftCrop = document.getElementById('oddLeftCrop');
        this.oddRightCrop = document.getElementById('oddRightCrop');
        this.evenTopCrop = document.getElementById('evenTopCrop');
        this.evenBottomCrop = document.getElementById('evenBottomCrop');
        this.evenLeftCrop = document.getElementById('evenLeftCrop');
        this.evenRightCrop = document.getElementById('evenRightCrop');
        
        // 裁剪预览元素
        this.previewCropBtn = document.getElementById('preview-crop-btn');
        this.cropPreviewModal = document.getElementById('cropPreviewModal');
        this.cropPreviewCanvas = document.getElementById('crop-preview-canvas');
        this.cropPageInfo = document.getElementById('crop-page-info');
        this.cropPageJump = document.getElementById('crop-page-jump');
        this.cropPageJumpBtn = document.getElementById('crop-page-jump-btn');
        this.cropPrevPageBtn = document.getElementById('crop-prev-page');
        this.cropNextPageBtn = document.getElementById('crop-next-page');
        this.cropOriginalSize = document.getElementById('crop-original-size');
        this.cropCroppedSize = document.getElementById('crop-cropped-size');
        
        // 页面设置预览元素
        this.previewPageSettingsBtn = document.getElementById('preview-page-settings-btn');
        this.pageSettingsPreviewModal = document.getElementById('pageSettingsPreviewModal');
        this.pageSettingsPreviewCanvas = document.getElementById('page-settings-preview-canvas');
        this.pageSettingsPageInfo = document.getElementById('page-settings-page-info');
        this.pageSettingsPageJump = document.getElementById('page-settings-page-jump');
        this.pageSettingsPageJumpBtn = document.getElementById('page-settings-page-jump-btn');
        this.pageSettingsPrevPageBtn = document.getElementById('page-settings-prev-page');
        this.pageSettingsNextPageBtn = document.getElementById('page-settings-next-page');
        
        // 页面设置翻页动画预览元素
        this.pageSettingsTransitionPreview = document.getElementById('page-settings-transition-preview');
        this.pageSettingsPreviewPage1 = document.getElementById('page-settings-preview-page-1');
        this.pageSettingsPreviewPage2 = document.getElementById('page-settings-preview-page-2');
        

        // 竖排双页模式复选框
        this.verticalLayout = document.getElementById('vertical-layout');
        
        // 页面排列顺序设置元素
        this.pageOrderSettings = document.getElementById('pageOrderSettings');
        this.oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
        this.oddLeftEvenRight = document.getElementById('oddLeftEvenRight');
        
        // 裁剪预览状态
        this.currentCropPage = 1;
        this.cropPdfDoc = null;
        
        // 页面设置预览状态
        this.currentPageSettingsPage = 1;
        this.pageSettingsPdfDoc = null;
        
        // 确保pageTimingSection初始状态正确
        if (this.pageTimingSection) {
            console.log('初始化: pageTimingSection元素已找到，当前显示状态:', window.getComputedStyle(this.pageTimingSection).display);
            // 确保初始状态为隐藏，除非有配置数据需要显示
            if (!this.pageTimings || this.pageTimings.length === 0) {
                this.pageTimingSection.style.display = 'none';
                console.log('初始化: 设置pageTimingSection为隐藏状态');
            }
        } else {
            console.error('初始化: pageTimingSection元素未找到');
        }
        
        // 确保日志区域在页面加载时是显示的
        const logSection = document.getElementById('log-section');
        const logContainer = document.getElementById('log-container');
        const logContent = document.getElementById('log-content');
        
        if (logSection) {
            logSection.style.display = 'block';
            console.log('✓ 日志区域已显示');
        } else {
            console.error('✗ 日志区域元素未找到');
        }
        
        if (logContainer) {
            console.log('✓ 日志容器已找到');
        } else {
            console.error('✗ 日志容器元素未找到');
        }
        
        if (logContent) {
            console.log('✓ 日志内容区域已找到');
        } else {
            console.error('✗ 日志内容区域元素未找到');
        }
        
        // 添加初始化日志
        this.addLogEntry('='.repeat(60), 'info');
        this.addLogEntry('系统初始化完成', 'success');
        this.addLogEntry('日志系统已就绪', 'success');
        this.addLogEntry('WebSocket连接初始化中...', 'info');
        this.addLogEntry('='.repeat(60), 'info');
        
        // 初始化导航菜单
        this.initializeNavigation();
    }

    initializeNavigation() {
        // 获取所有导航链接
        const navLinks = document.querySelectorAll('.nav-link[data-section]');
        
        // 为每个导航链接添加点击事件
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                
                // 获取目标section的ID
                const targetSectionId = link.getAttribute('data-section');
                const targetSection = document.getElementById(targetSectionId);
                
                if (targetSection) {
                    // 移除所有导航链接的active类
                    navLinks.forEach(navLink => {
                        navLink.classList.remove('active');
                    });
                    
                    // 为当前点击的链接添加active类
                    link.classList.add('active');
                    
                    // 滚动到目标section
                    targetSection.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                    
                    // 添加日志
                    this.addLogEntry(`导航到: ${link.textContent.trim()}`, 'info');
                }
            });
        });
        
        // 监听页面滚动，更新导航状态
        window.addEventListener('scroll', () => {
            this.updateActiveNavigation();
        });
    }

    updateActiveNavigation() {
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.nav-link[data-section]');
        
        let currentSection = '';
        
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            
            if (window.pageYOffset >= sectionTop - 100) {
                currentSection = section.getAttribute('id');
            }
        });
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('data-section') === currentSection) {
                link.classList.add('active');
            }
        });
    }

    setDefaultValues() {
        // Set PDF page ranges to empty by default
        if (this.startPage) this.startPage.value = '';
        if (this.endPage) this.endPage.value = '';
        if (this.timingStartPage) this.timingStartPage.value = '';
        if (this.timingEndPage) this.timingEndPage.value = '';
        
        // Set default resolution to 720p
        if (this.resolution) {
            this.resolution.value = '1280x720';
        }
    }

    initializeToggleStates() {
        // 初始化竖排双页模式的禁用/启用状态
        if (this.verticalLayout && this.pageOrderSettings) {
            const pageOrderElements = this.pageOrderSettings.querySelectorAll('input, label');
            pageOrderElements.forEach(element => {
                if (this.verticalLayout.checked) {
                    element.removeAttribute('disabled');
                } else {
                    element.setAttribute('disabled', 'disabled');
                }
            });
        }
        
        // 初始化PDF边界裁剪设置的禁用/启用状态
        if (this.enableCrop && this.cropSettings) {
            const cropElements = this.cropSettings.querySelectorAll('input, label, button');
            cropElements.forEach(element => {
                if (this.enableCrop.checked) {
                    element.removeAttribute('disabled');
                } else {
                    element.setAttribute('disabled', 'disabled');
                }
            });
        }
        
        // 确保页面加载完成后，竖排双页模式的启用状态正确设置
        setTimeout(() => {
            if (this.verticalLayout && this.pageOrderSettings) {
                const pageOrderElements = this.pageOrderSettings.querySelectorAll('input, label');
                pageOrderElements.forEach(element => {
                    if (this.verticalLayout.checked) {
                        element.removeAttribute('disabled');
                    } else {
                        element.setAttribute('disabled', 'disabled');
                    }
                });
            }
        }, 100);
    }

    bindEvents() {
        // File upload events
        this.fileInput.addEventListener('change', (e) => this.handleFileSelection(e));

        // Upload area click events
        this.uploadAreas.forEach(area => {
            area.addEventListener('click', (e) => {
                if (!e.target.closest('button') && !e.target.closest('input')) {
                    const type = area.dataset.type;
                    this.selectFileForType(type);
                }
            });
            area.addEventListener('dragover', (e) => this.handleDragOver(e));
            area.addEventListener('drop', (e) => this.handleDrop(e));
        });
        
        // Config upload area click event
        if (this.configUploadArea) {
            this.configUploadArea.addEventListener('click', (e) => {
                if (!e.target.closest('button') && !e.target.closest('input')) {
                    this.selectFileForType('config');
                }
            });
            this.configUploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
            this.configUploadArea.addEventListener('drop', (e) => this.handleDrop(e));
            
            // 添加悬浮预览事件
            this.configUploadArea.addEventListener('mouseenter', () => this.showConfigUploadPreview());
            this.configUploadArea.addEventListener('mouseleave', () => this.hideConfigUploadPreview());
        }
        
        // Video upload area click event
        if (this.videoUploadArea) {
            this.videoUploadArea.addEventListener('click', (e) => {
                if (!e.target.closest('button') && !e.target.closest('input')) {
                    this.selectFileForType('video');
                }
            });
            this.videoUploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
            this.videoUploadArea.addEventListener('drop', (e) => this.handleDrop(e));
        }

        // Generate timings from subtitles button
        this.generateTimingsFromSubsBtn.addEventListener('click', () => {
            this.generateTimingsFromSubtitles();
        });

        // Extract subtitle button
        if (this.extractSubtitleBtn) {
            this.extractSubtitleBtn.addEventListener('click', () => {
                this.extractSubtitle();
            });
        }

        // Reset timings button
        this.resetTimingsBtn = document.getElementById('reset-timings');
        if (this.resetTimingsBtn) {
            this.resetTimingsBtn.addEventListener('click', () => {
                this.resetTimings();
            });
        }

        // Load timings button
        this.loadTimingsBtn = document.getElementById('load-timings');
        if (this.loadTimingsBtn) {
            this.loadTimingsBtn.addEventListener('click', () => {
                this.loadPageTimingsData();
            });
        }

        // Save config button
        this.saveConfigBtn = document.getElementById('save-config');
        if (this.saveConfigBtn) {
            this.saveConfigBtn.addEventListener('click', async () => {
                const success = await this.savePageTimingsData();
                if (success) {
                    this.showSuccess('配置已保存');
                } else {
                    this.showError('配置保存失败');
                }
            });
        }

        // Load config button
        this.loadConfigBtn = document.getElementById('load-config');
        if (this.loadConfigBtn) {
            console.log('找到加载配置按钮元素');
            this.loadConfigBtn.addEventListener('click', async () => {
                console.log('加载配置按钮被点击');
                console.log('当前uploadedFiles状态:', this.uploadedFiles);
                await this.loadPageTimingsData();
            });
        } else {
            console.error('未找到加载配置按钮元素');
        }

        // Page range change events
        this.timingStartPage.addEventListener('change', () => {
            this.generatePageTimingInputs();
            const startPage = parseInt(this.timingStartPage.value) || 1;
            const endPage = parseInt(this.timingEndPage.value) || this.pageCount;
            this.updatePageCountDisplay(endPage - startPage);
        });

        this.timingEndPage.addEventListener('change', () => {
            this.generatePageTimingInputs();
            const startPage = parseInt(this.timingStartPage.value) || 1;
            const endPage = parseInt(this.timingEndPage.value) || this.pageCount;
            this.updatePageCountDisplay(endPage - startPage);
        });

        // Vertical layout change event
        this.verticalLayout.addEventListener('change', () => {
            // 启用或禁用页面排列顺序设置
            const pageOrderElements = this.pageOrderSettings.querySelectorAll('input, label');
            pageOrderElements.forEach(element => {
                if (this.verticalLayout.checked) {
                    element.removeAttribute('disabled');
                } else {
                    element.setAttribute('disabled', 'disabled');
                }
            });
            
            // 当竖排布局选项改变时，重新生成翻页点输入框
            this.generatePageTimingInputs();
            const startPage = parseInt(this.timingStartPage.value) || 1;
            const endPage = parseInt(this.timingEndPage.value) || this.pageCount;
            this.updatePageCountDisplay(endPage - startPage);
        });

        // Settings change events
        this.quality.addEventListener('change', () => this.updateEstimatedSize());
        this.bitrate.addEventListener('change', () => this.updateEstimatedSize());
        this.resolution.addEventListener('change', () => this.updateEstimatedSize());

        // Create video button
        this.createVideoBtn.addEventListener('click', () => this.createVideo());

        // Preview video button
        if (this.previewVideoBtn) {
            this.previewVideoBtn.addEventListener('click', () => {
                // 获取书名和视频文件名
                const bookName = this.previewVideoBtn.getAttribute('data-book-name') || this.getCurrentBookName();
                const videoFilename = this.previewVideoBtn.getAttribute('data-video-filename');
                
                if (bookName && videoFilename) {
                    this.showVideoPreview(bookName, videoFilename);
                } else {
                    this.showVideoPreview();
                }
            });
        }

        // Log control buttons
        if (this.clearLogBtn) {
            this.clearLogBtn.addEventListener('click', () => {
                this.clearLog();
            });
        }

        if (this.toggleLogBtn) {
            this.toggleLogBtn.addEventListener('click', () => {
                this.toggleLog();
            });
        }
        
        // Toggle UI logging button
        const toggleUILogBtn = document.getElementById('toggle-ui-log-btn');
        if (toggleUILogBtn) {
            toggleUILogBtn.addEventListener('click', () => {
                this.toggleUILogging();
                // 更新按钮图标
                if (this.disableUILogging) {
                    toggleUILogBtn.innerHTML = '<i class="bi bi-eye-slash me-1"></i> 界面日志';
                } else {
                    toggleUILogBtn.innerHTML = '<i class="bi bi-eye me-1"></i> 界面日志';
                }
            });
        }

        // Preview events
        document.addEventListener('click', (e) => {
            if (e.target.closest('.preview-pdf-btn')) {
                this.showPdfHoverPreview();
            }
            if (e.target.closest('.preview-subs-btn')) {
                this.showSubsHoverPreview();
            }
            if (e.target.closest('.preview-config-btn')) {
                this.showConfigHoverPreview();
            }
            if (e.target.closest('.preview-video-btn')) {
                const videoPreviewModal = new bootstrap.Modal(document.getElementById('videoPreviewModal'));
                videoPreviewModal.show();
            }
        });

        // PDF preview navigation events
        if (this.pdfPrevPageBtn) {
            this.pdfPrevPageBtn.addEventListener('click', async () => {
                if (this.currentPdfPage > 1) {
                    this.currentPdfPage--;
                    await this.renderPdfPage();
                }
            });
        }

        if (this.pdfNextPageBtn) {
            this.pdfNextPageBtn.addEventListener('click', async () => {
                if (this.pdfDoc && this.currentPdfPage < this.pdfDoc.numPages) {
                    this.currentPdfPage++;
                    await this.renderPdfPage();
                }
            });
        }

        if (this.pdfPageJumpBtn) {
            this.pdfPageJumpBtn.addEventListener('click', async () => {
                const pageNum = parseInt(this.pdfPageJump.value);
                if (this.pdfDoc && pageNum >= 1 && pageNum <= this.pdfDoc.numPages) {
                    this.currentPdfPage = pageNum;
                    await this.renderPdfPage();
                }
            });
        }

        // PDF modal events - load PDF when modal is opened
        if (this.pdfPreviewModal) {
            // Add event listener for when modal is showing
            this.pdfPreviewModal.addEventListener('show.bs.modal', () => {
                console.log('PDF预览模态框正在显示');
                // 重置页码
                this.currentPdfPage = 1;
                // 在模态框显示时立即初始化canvas
                this.initializePdfCanvas();
            });
            
            // Add event listener for when modal is shown
            this.pdfPreviewModal.addEventListener('shown.bs.modal', () => {
                console.log('PDF预览模态框已显示，准备加载PDF');
                // 检查是否已经在加载中，避免重复加载
                if (!this.pdfLoading) {
                    this.pdfLoading = true;
                    // 延迟加载PDF以确保模态框完全显示
                    setTimeout(() => {
                        console.log('延迟加载PDF');
                        this.loadPdfForPreview().finally(() => {
                            this.pdfLoading = false;
                        });
                    }, 300); // 减少延迟时间
                } else {
                    console.log('PDF已在加载中，跳过重复加载');
                }
            });
            
            // Add event listener for when modal is hidden
            this.pdfPreviewModal.addEventListener('hidden.bs.modal', () => {
                console.log('PDF预览模态框已隐藏，清理资源');
                // 重置PDF加载状态
                this.pdfLoading = false;
                // 清理PDF文档和渲染任务
                this.cleanupPdfResources();
            });
        }

        // Video modal shown event - load video when modal is opened
        if (this.videoPreviewModal) {
            this.videoPreviewModal.addEventListener('shown.bs.modal', () => {
                this.loadVideoForPreview();
            });
            
            // Add event listener for when modal is hidden
            this.videoPreviewModal.addEventListener('hidden.bs.modal', () => {
                // Pause video when modal is closed
                if (this.videoPreviewPlayer) {
                    this.videoPreviewPlayer.pause();
                }
            });
        }

        // Transition effect preview button
        const previewTransitionBtn = document.getElementById('preview-transition-btn');
        if (previewTransitionBtn) {
            previewTransitionBtn.addEventListener('click', () => {
                this.previewTransitionEffect();
            });
        }

        // Close transition preview button
        const closeTransitionPreview = document.getElementById('close-transition-preview');
        if (closeTransitionPreview) {
            closeTransitionPreview.addEventListener('click', () => {
                const previewContainer = document.getElementById('transition-preview-container');
                if (previewContainer) {
                    previewContainer.style.display = 'none';
                }
            });
        }

        // 翻页效果选择器变化事件
        const transitionEffect = document.getElementById('transition-effect');
        if (transitionEffect) {
            transitionEffect.addEventListener('change', () => {
                // 更新主预览区域的翻页效果
                this.previewTransitionEffect();

                // 注释掉自动触发页面设置预览的翻页效果，避免覆盖PDF预览
                // 如果页面设置预览模态框是显示状态，也更新那里的预览
                // if (this.pageSettingsPreviewModal) {
                //     const modal = bootstrap.Modal.getInstance(this.pageSettingsPreviewModal);
                //     if (modal && modal._isShown) {
                //         // this.previewPageSettingsTransition(); // 禁用自动翻页效果，保持PDF预览显示
                //     }
                // }
            });
        }

        // Open directory button
        this.openDirectoryBtn = document.getElementById('open-directory-btn');
        

        if (this.openDirectoryBtn) {
            this.openDirectoryBtn.addEventListener('click', () => {
                this.openLocalDirectory();
            });
        }
        
        // 裁剪设置事件
        if (this.enableCrop) {
            this.enableCrop.addEventListener('change', () => {
                // 启用或禁用裁剪设置
                const cropElements = this.cropSettings.querySelectorAll('input, label, button');
                cropElements.forEach(element => {
                    if (this.enableCrop.checked) {
                        element.removeAttribute('disabled');
                    } else {
                        element.setAttribute('disabled', 'disabled');
                    }
                });
            });
        }
        
        // 裁剪预览按钮事件
        if (this.previewCropBtn) {
            this.previewCropBtn.addEventListener('click', () => {
                this.showCropPreview();
            });
        }
        
        // 裁剪预览导航事件
        if (this.cropPrevPageBtn) {
            this.cropPrevPageBtn.addEventListener('click', () => {
                // 检查是否启用了竖排双页模式
                const verticalLayout = document.getElementById('vertical-layout');
                const isVerticalLayout = verticalLayout && verticalLayout.checked;
                
                if (isVerticalLayout) {
                    // 获取页面排列顺序设置
                const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                    
                    if (isOddRightEvenLeft) {
                        // 奇数页在右侧，偶数页在左边：每次翻两页
                        if (this.currentCropPage > 2) {
                            this.currentCropPage -= 2;
                            this.renderCropPage();
                        }
                    } else {
                        // 奇数页在左边，偶数页在右边：每次翻两页
                        if (this.currentCropPage > 2) {
                            this.currentCropPage -= 2;
                            this.renderCropPage();
                        }
                    }
                } else {
                    // 普通模式：每次翻一页
                    if (this.currentCropPage > 1) {
                        this.currentCropPage--;
                        this.renderCropPage();
                    }
                }
            });
        }

        if (this.cropNextPageBtn) {
            this.cropNextPageBtn.addEventListener('click', () => {
                if (this.cropPdfDoc) {
                    // 检查是否启用了竖排双页模式
                    const verticalLayout = document.getElementById('vertical-layout');
                    const isVerticalLayout = verticalLayout && verticalLayout.checked;
                    
                    if (isVerticalLayout) {
                        // 获取页面排列顺序设置
                        const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                        const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                        
                        if (isOddRightEvenLeft) {
                            // 奇数页在右侧，偶数页在左边：每次翻两页
                            if (this.cropPdfDoc && this.currentCropPage < this.cropPdfDoc.numPages - 1) {
                                this.currentCropPage += 2;
                                this.renderCropPage();
                            }
                        } else {
                            // 奇数页在左边，偶数页在右边：每次翻两页
                            if (this.cropPdfDoc && this.currentCropPage < this.cropPdfDoc.numPages - 1) {
                                this.currentCropPage += 2;
                                this.renderCropPage();
                            }
                        }
                    } else {
                        // 普通模式：每次翻一页
                        if (this.cropPdfDoc && this.currentCropPage < this.cropPdfDoc.numPages) {
                            this.currentCropPage++;
                            this.renderCropPage();
                        }
                    }
                }
            });
        }

        if (this.cropPageJumpBtn) {
            this.cropPageJumpBtn.addEventListener('click', () => {
                const pageNum = parseInt(this.cropPageJump.value);
                if (this.cropPdfDoc && pageNum >= 1 && pageNum <= this.cropPdfDoc.numPages) {
                    // 检查是否启用了竖排双页模式
                    const verticalLayout = document.getElementById('vertical-layout');
                    const isVerticalLayout = verticalLayout && verticalLayout.checked;
                    
                    if (isVerticalLayout) {
                        // 获取页面排列顺序设置
                const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                        
                        if (isOddRightEvenLeft) {
                            // 奇数页在右侧，偶数页在左边：确保跳转到奇数页（右页）
                            if (pageNum % 2 === 0) {
                                // 如果是偶数页，跳转到前一页（奇数页）
                                this.currentCropPage = pageNum - 1;
                            } else {
                                // 已经是奇数页，直接跳转
                                this.currentCropPage = pageNum;
                            }
                        } else {
                            // 奇数页在左边，偶数页在右边：直接跳转到输入的页码
                            this.currentCropPage = pageNum;
                        }
                    } else {
                        // 普通模式：直接跳转
                        this.currentCropPage = pageNum;
                    }
                    this.renderCropPage();
                }
            });
        }
        
        // 裁剪预览模态框显示事件
        if (this.cropPreviewModal) {
            this.cropPreviewModal.addEventListener('shown.bs.modal', () => {
                this.loadPdfForCropPreview();
            });
        }
        
        // 页面设置预览按钮事件
        if (this.previewPageSettingsBtn) {
            this.previewPageSettingsBtn.addEventListener('click', async () => {
                await this.showPageSettingsPreview();
            });
        }
        
        // 页面设置预览导航事件
        if (this.pageSettingsPrevPageBtn) {
            this.pageSettingsPrevPageBtn.addEventListener('click', () => {
                // 检查是否启用了竖排双页模式
                const verticalLayout = document.getElementById('vertical-layout');
                const isVerticalLayout = verticalLayout && verticalLayout.checked;
                
                if (isVerticalLayout) {
                    // 获取页面排列顺序设置
                    const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                    const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                    
                    if (isOddRightEvenLeft) {
                        // 奇数页在右侧，偶数页在左边：每次翻两页
                        if (this.currentPageSettingsPage > 2) {
                            this.currentPageSettingsPage -= 2;
                            this.renderPageSettingsPage();
                            // 添加翻页效果预览
                            setTimeout(() => {
                                // 清除之前的翻页效果
                                if (window.pageSettingsFlipEffect) {
                                    window.pageSettingsFlipEffect.destroy();
                                    window.pageSettingsFlipEffect = null;
                                }
                                
                                // 移除翻页容器
                                const flipContainer = document.getElementById('page-settings-flip-container');
                                if (flipContainer) {
                                    flipContainer.remove();
                                }
                                
                                // 显示原始canvas
                                const canvas = document.getElementById('page-settings-preview-canvas');
                                if (canvas) {
                                    canvas.style.display = 'block';
                                }
                                
                                // 重新创建翻页效果
                                // this.previewPageSettingsTransition(); // 已禁用翻页效果预览
                            }, 500);
                        }
                    } else {
                        // 奇数页在左边，偶数页在右边：每次翻两页
                        if (this.currentPageSettingsPage > 2) {
                            this.currentPageSettingsPage -= 2;
                            this.renderPageSettingsPage();
                            // 添加翻页效果预览
                            setTimeout(() => {
                                // 清除之前的翻页效果
                                if (window.pageSettingsFlipEffect) {
                                    window.pageSettingsFlipEffect.destroy();
                                    window.pageSettingsFlipEffect = null;
                                }
                                
                                // 移除翻页容器
                                const flipContainer = document.getElementById('page-settings-flip-container');
                                if (flipContainer) {
                                    flipContainer.remove();
                                }
                                
                                // 显示原始canvas
                                const canvas = document.getElementById('page-settings-preview-canvas');
                                if (canvas) {
                                    canvas.style.display = 'block';
                                }
                                
                                // 重新创建翻页效果
                                // this.previewPageSettingsTransition(); // 已禁用翻页效果预览
                            }, 500);
                        }
                    }
                } else {
                    // 普通模式：每次翻一页
                    if (this.currentPageSettingsPage > 1) {
                        this.currentPageSettingsPage--;
                        this.renderPageSettingsPage();
                        // 添加翻页效果预览
                        setTimeout(() => {
                            // 清除之前的翻页效果
                            if (window.pageSettingsFlipEffect) {
                                window.pageSettingsFlipEffect.destroy();
                                window.pageSettingsFlipEffect = null;
                            }
                            
                            // 移除翻页容器
                            const flipContainer = document.getElementById('page-settings-flip-container');
                            if (flipContainer) {
                                flipContainer.remove();
                            }
                            
                            // 显示原始canvas
                            const canvas = document.getElementById('page-settings-preview-canvas');
                            if (canvas) {
                                canvas.style.display = 'block';
                            }
                            
                            // 重新创建翻页效果
                            // this.previewPageSettingsTransition(); // 禁用自动翻页效果，保持PDF预览显示
                        }, 500);
                    }
                }
            });
        }

        if (this.pageSettingsNextPageBtn) {
            this.pageSettingsNextPageBtn.addEventListener('click', () => {
                if (this.pageSettingsPdfDoc) {
                    // 检查是否启用了竖排双页模式
                    const verticalLayout = document.getElementById('vertical-layout');
                    const isVerticalLayout = verticalLayout && verticalLayout.checked;
                    
                    if (isVerticalLayout) {
                        // 获取页面排列顺序设置
                        const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                        const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                        
                        if (isOddRightEvenLeft) {
                            // 奇数页在右侧，偶数页在左边：每次翻两页
                            if (this.pageSettingsPdfDoc && this.currentPageSettingsPage < this.pageSettingsPdfDoc.numPages - 1) {
                            this.currentPageSettingsPage += 2;
                            this.renderPageSettingsPage();
                            // 添加翻页效果预览
                            setTimeout(() => {
                                // 清除之前的翻页效果
                                if (window.pageSettingsFlipEffect) {
                                    window.pageSettingsFlipEffect.destroy();
                                    window.pageSettingsFlipEffect = null;
                                }
                                
                                // 移除翻页容器
                                const flipContainer = document.getElementById('page-settings-flip-container');
                                if (flipContainer) {
                                    flipContainer.remove();
                                }
                                
                                // 显示原始canvas
                                const canvas = document.getElementById('page-settings-preview-canvas');
                                if (canvas) {
                                    canvas.style.display = 'block';
                                }
                                
                                // 重新创建翻页效果
                                // this.previewPageSettingsTransition(); // 已禁用翻页效果预览
                            }, 500);
                        }
                        } else {
                            // 奇数页在左边，偶数页在右边：每次翻两页
                            if (this.pageSettingsPdfDoc && this.currentPageSettingsPage < this.pageSettingsPdfDoc.numPages - 1) {
                            this.currentPageSettingsPage += 2;
                            this.renderPageSettingsPage();
                            // 添加翻页效果预览
                            setTimeout(() => {
                                // 清除之前的翻页效果
                                if (window.pageSettingsFlipEffect) {
                                    window.pageSettingsFlipEffect.destroy();
                                    window.pageSettingsFlipEffect = null;
                                }
                                
                                // 移除翻页容器
                                const flipContainer = document.getElementById('page-settings-flip-container');
                                if (flipContainer) {
                                    flipContainer.remove();
                                }
                                
                                // 显示原始canvas
                                const canvas = document.getElementById('page-settings-preview-canvas');
                                if (canvas) {
                                    canvas.style.display = 'block';
                                }
                                
                                // 重新创建翻页效果
                                // this.previewPageSettingsTransition(); // 已禁用翻页效果预览
                            }, 500);
                        }
                        }
                    } else {
                        // 普通模式：每次翻一页
                        if (this.pageSettingsPdfDoc && this.currentPageSettingsPage < this.pageSettingsPdfDoc.numPages) {
                            this.currentPageSettingsPage++;
                            this.renderPageSettingsPage();
                            // 添加翻页效果预览
                            setTimeout(() => {
                                // 清除之前的翻页效果
                                if (window.pageSettingsFlipEffect) {
                                    window.pageSettingsFlipEffect.destroy();
                                    window.pageSettingsFlipEffect = null;
                                }
                                
                                // 移除翻页容器
                                const flipContainer = document.getElementById('page-settings-flip-container');
                                if (flipContainer) {
                                    flipContainer.remove();
                                }
                                
                                // 显示原始canvas
                                const canvas = document.getElementById('page-settings-preview-canvas');
                                if (canvas) {
                                    canvas.style.display = 'block';
                                }
                                
                                // 重新创建翻页效果
                                // this.previewPageSettingsTransition(); // 已禁用翻页效果预览
                            }, 500);
                        }
                    }
                }
            });
        }

        if (this.pageSettingsPageJumpBtn) {
            this.pageSettingsPageJumpBtn.addEventListener('click', () => {
                const pageNum = parseInt(this.pageSettingsPageJump.value);
                if (this.pageSettingsPdfDoc && pageNum >= 1 && pageNum <= this.pageSettingsPdfDoc.numPages) {
                    // 检查是否启用了竖排双页模式
                    const verticalLayout = document.getElementById('vertical-layout');
                    const isVerticalLayout = verticalLayout && verticalLayout.checked;
                    
                    if (isVerticalLayout) {
                        // 获取页面排列顺序设置
                        const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                        const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                        
                        if (isOddRightEvenLeft) {
                            // 奇数页在右侧，偶数页在左边：确保跳转到奇数页（右页）
                            if (pageNum % 2 === 0) {
                                // 如果是偶数页，跳转到前一页（奇数页）
                                this.currentPageSettingsPage = pageNum - 1;
                            } else {
                                // 已经是奇数页，直接跳转
                                this.currentPageSettingsPage = pageNum;
                            }
                        } else {
                            // 奇数页在左边，偶数页在右边：直接跳转到输入的页码
                            this.currentPageSettingsPage = pageNum;
                        }
                    } else {
                        // 普通模式：直接跳转
                        this.currentPageSettingsPage = pageNum;
                    }
                    this.renderPageSettingsPage();
                    // 添加翻页效果预览
                    setTimeout(() => {
                        // 清除之前的翻页效果
                        if (window.pageSettingsFlipEffect) {
                            window.pageSettingsFlipEffect.destroy();
                            window.pageSettingsFlipEffect = null;
                        }
                        
                        // 移除翻页容器
                        const flipContainer = document.getElementById('page-settings-flip-container');
                        if (flipContainer) {
                            flipContainer.remove();
                        }
                        
                        // 显示原始canvas
                        const canvas = document.getElementById('page-settings-preview-canvas');
                        if (canvas) {
                            canvas.style.display = 'block';
                        }
                        
                        // 重新创建翻页效果
                        // this.previewPageSettingsTransition(); // 禁用自动翻页效果，保持PDF预览显示
                    }, 500);
                }
            });
        }
        
        // 页面设置预览模态框显示事件
        if (this.pageSettingsPreviewModal) {
            this.pageSettingsPreviewModal.addEventListener('shown.bs.modal', async () => {
                try {
                    // 始终重新加载PDF，确保PDF文档可用
                    await this.loadPdfForPageSettingsPreview();

                    // 不再显示翻页效果预览，只显示PDF内容
                    // setTimeout(() => {
                    //     this.previewPageSettingsTransition();
                    // }, 2000);

                    console.log('PDF预览已加载，页面设置预览功能正常');
                } catch (error) {
                    console.error('页面设置预览初始化失败:', error);
                    this.showError('页面设置预览初始化失败');
                }
            });
            
            // 页面设置预览模态框隐藏事件，清理翻页效果
            this.pageSettingsPreviewModal.addEventListener('hidden.bs.modal', () => {
                // 清除翻页效果
                if (window.pageSettingsFlipEffect) {
                    window.pageSettingsFlipEffect.destroy();
                    window.pageSettingsFlipEffect = null;
                }
                
                // 移除翻页容器
                const flipContainer = document.getElementById('page-settings-flip-container');
                if (flipContainer) {
                    flipContainer.remove();
                }
                
                // 清理PDF文档
                this.pageSettingsPdfDoc = null;
                
                // 清除画布内容
                const canvas = document.getElementById('page-settings-preview-canvas');
                if (canvas) {
                    const context = canvas.getContext('2d');
                    context.clearRect(0, 0, canvas.width, canvas.height);
                    canvas.style.display = 'block';
                }
            });
        }
        
        // 竖排双页模式改变事件
        if (this.verticalLayout) {
            this.verticalLayout.addEventListener('change', () => {
                // 更新页面排列顺序选项的禁用/启用状态
                if (this.pageOrderSettings) {
                    const pageOrderElements = this.pageOrderSettings.querySelectorAll('input, label');
                    pageOrderElements.forEach(element => {
                        if (this.verticalLayout.checked) {
                            element.removeAttribute('disabled');
                        } else {
                            element.setAttribute('disabled', 'disabled');
                        }
                    });
                }
                
                // 如果PDF已加载，重新渲染当前页面
                if (this.cropPdfDoc) {
                    // 获取页面排列顺序设置
                    const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                    const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                    
                    // 在竖排模式下，根据页面排列顺序设置调整当前页
                    if (this.verticalLayout.checked) {
                        if (isOddRightEvenLeft) {
                            // 奇数页在右侧，偶数页在左边：确保当前页是奇数页
                            if (this.currentCropPage % 2 === 0) {
                                this.currentCropPage = Math.max(1, this.currentCropPage - 1);
                            }
                        }
                        // 如果是奇数页在左边，偶数页在右边，则不需要调整页码
                    }
                    this.renderCropPage();
                }
            });
        }
        
        // Audio filename hover events - REMOVED
        // if (this.audioFilenameHover) {
        //     this.audioFilenameHover.addEventListener('mouseenter', () => {
        //         this.audioHoverShowTimeout = setTimeout(() => {
        //             this.showAudioHoverPlayer();
        //         }, 500);
        //     });
        //     
        //     this.audioFilenameHover.addEventListener('mouseleave', () => {
        //         clearTimeout(this.audioHoverShowTimeout);
        //         setTimeout(() => {
        //             if (!this.audioHoverPinned && !this.audioHoverPlayer.matches(':hover')) {
        //                 this.hideAudioHoverPlayer();
        //             }
        //         }, 300);
        //     });
        // }
        
        // Audio hover player events - REMOVED
        // if (this.audioHoverPlayer) {
        //     this.audioHoverPlayer.addEventListener('mouseenter', () => {
        //         clearTimeout(this.audioHoverTimeout);
        //     });
        //     
        //     this.audioHoverPlayer.addEventListener('mouseleave', () => {
        //         if (!this.audioHoverPinned) {
        //             this.hideAudioHoverPlayer();
        //         }
        //     });
        // }
        
        // Audio pin button event - REMOVED
        // if (this.audioPinBtn) {
        //     this.audioPinBtn.addEventListener('click', () => {
        //         this.toggleAudioHoverPin();
        //     });
        // }
        
        // Audio close button event - REMOVED
        // if (this.audioCloseBtn) {
        //     this.audioCloseBtn.addEventListener('click', () => {
        //         this.closeAudioHoverPlayer();
        //     });
        // }
        
        // PDF filename hover events - REMOVED
        // if (this.pdfFilenameHover) {
        //     this.pdfFilenameHover.addEventListener('mouseenter', () => {
        //         this.pdfHoverShowTimeout = setTimeout(() => {
        //             this.showPdfHoverPreview();
        //         }, 500);
        //     });
        //     
        //     this.pdfFilenameHover.addEventListener('mouseleave', () => {
        //         clearTimeout(this.pdfHoverShowTimeout);
        //         setTimeout(() => {
        //             if (!this.pdfHoverPreview.matches(':hover')) {
        //                 this.hidePdfHoverPreview();
        //             }
        //         }, 300);
        //     });
        // }
        
        // PDF hover preview events - REMOVED
        // if (this.pdfHoverPreview) {
        //     this.pdfHoverPreview.addEventListener('mouseenter', () => {
        //         clearTimeout(this.pdfHoverTimeout);
        //     });
        //     
        //     this.pdfHoverPreview.addEventListener('mouseleave', () => {
        //         this.hidePdfHoverPreview();
        //     });
        // }
        
        // Subtitle filename hover events - REMOVED
        // if (this.subsFilenameHover) {
        //     this.subsFilenameHover.addEventListener('mouseenter', () => {
        //         this.subsHoverShowTimeout = setTimeout(() => {
        //             this.showSubsHoverPreview();
        //         }, 500);
        //     });
        //     
        //     this.subsFilenameHover.addEventListener('mouseleave', () => {
        //         clearTimeout(this.subsHoverShowTimeout);
        //         setTimeout(() => {
        //             if (!this.subsHoverPreview.matches(':hover')) {
        //                 this.hideSubsHoverPreview();
        //             }
        //         }, 300);
        //     });
        // }
        
        // Subtitle hover preview events - REMOVED
        // if (this.subsHoverPreview) {
        //     this.subsHoverPreview.addEventListener('mouseenter', () => {
        //         clearTimeout(this.subsHoverTimeout);
        //     });
        //     
        //     this.subsHoverPreview.addEventListener('mouseleave', () => {
        //         this.hideSubsHoverPreview();
        //     });
        // }
        
        // Config filename hover events - REMOVED
        // if (this.configFilenameHover) {
        //     this.configFilenameHover.addEventListener('mouseenter', () => {
        //         this.configHoverShowTimeout = setTimeout(() => {
        //             this.showConfigHoverPreview();
        //         }, 500);
        //     });
        //     
        //     this.configFilenameHover.addEventListener('mouseleave', () => {
        //         clearTimeout(this.configHoverShowTimeout);
        //         setTimeout(() => {
        //             if (!this.configHoverPreview.matches(':hover')) {
        //                 this.hideConfigHoverPreview();
        //             }
        //         }, 300);
        //     });
        // }
        
        // Config hover preview events - REMOVED
        // if (this.configHoverPreview) {
        //     this.configHoverPreview.addEventListener('mouseenter', () => {
        //         clearTimeout(this.configHoverTimeout);
        //     });
        //     
        //     this.configHoverPreview.addEventListener('mouseleave', () => {
        //         this.hideConfigHoverPreview();
        //     });
        // }
        
        // Video filename hover events - REMOVED
        // if (this.videoFilenameHover) {
        //     this.videoFilenameHover.addEventListener('mouseenter', () => {
        //         this.videoHoverShowTimeout = setTimeout(() => {
        //             this.showVideoHoverPreview();
        //         }, 500);
        //     });
        //     
        //     this.videoFilenameHover.addEventListener('mouseleave', () => {
        //         clearTimeout(this.videoHoverShowTimeout);
        //         this.videoHoverTimeout = setTimeout(() => {
        //             if (!this.videoHoverPreview.matches(':hover')) {
        //                 this.hideVideoHoverPreview();
        //             }
        //         }, 300);
        //     });
        // }
        
        // Video hover preview events - REMOVED
        // if (this.videoHoverPreview) {
        //     this.videoHoverPreview.addEventListener('mouseenter', () => {
        //         clearTimeout(this.videoHoverTimeout);
        //     });
        //     
        //     this.videoHoverPreview.addEventListener('mouseleave', () => {
        //         this.hideVideoHoverPreview();
        //     });
        // }
        
        // Refresh button event - 已移除处理历史功能
        
        // Extract subtitle button event
        const extractSubtitleBtn = document.getElementById('extract-subtitle-btn');
        if (extractSubtitleBtn) {
            extractSubtitleBtn.addEventListener('click', () => {
                this.extractSubtitleFromAudio();
            });
        }

        // Whisper model select change event
        const whisperModelSelect = document.getElementById('whisper-model-select');
        if (whisperModelSelect) {
            whisperModelSelect.addEventListener('change', () => {
                this.updateModelInfo();
            });
        }

        // 字幕文件选择框change事件
        if (this.subtitleFileSelect) {
            this.subtitleFileSelect.addEventListener('change', () => {
                const selectedOption = this.subtitleFileSelect.options[this.subtitleFileSelect.selectedIndex];
                if (selectedOption.value) {
                    console.log('已选择字幕文件:', selectedOption.value);
                    // 可以在这里添加预加载字幕文件的逻辑
                    // 或者只是记录用户的选择，等待点击"加载字幕内容"按钮
                }
            });
        }


    }

    async checkFFmpegStatus() {
        try {
            // 添加超时控制，避免长时间等待
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时
            
            const response = await fetch('/api/check-ffmpeg', {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const data = await response.json();

            if (data.available) {
                this.ffmpegStatus.innerHTML = `
                    <span class="badge bg-success me-2">FFmpeg已就绪</span>
                `;
            } else {
                this.ffmpegStatus.innerHTML = `
                    <span class="badge bg-danger me-2">FFmpeg未安装</span>
                    <i class="bi bi-x-circle text-danger"></i>
                `;
                this.showError('FFmpeg未安装，请先安装FFmpeg：brew install ffmpeg');
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.warn('FFmpeg检查超时');
            }
            this.ffmpegStatus.innerHTML = `
                <span class="badge bg-warning me-2">检查失败</span>
                <i class="bi bi-exclamation-triangle text-warning"></i>
            `;
        }
    }

    selectFileForType(type) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = {
            'pdf': '.pdf',
            'audio': '.m4a,.mp3,.wav',
            'subs': '.srt',
            'config': '.json,.config',
            'video': '.mp4,.mov,.avi,.mkv'
        }[type];

        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.uploadFile(e.target.files[0], type);
            }
        });

        // Add the input to the DOM temporarily to ensure it works in all browsers
        document.body.appendChild(input);
        
        // Trigger the click event
        input.click();
        
        // Remove the input from the DOM after a short delay
        setTimeout(() => {
            document.body.removeChild(input);
        }, 1000);
    }

    handleDragOver(e) {
        e.preventDefault();
        e.currentTarget.classList.add('border-primary');
    }

    handleDrop(e) {
        e.preventDefault();
        e.currentTarget.classList.remove('border-primary');

        const files = Array.from(e.dataTransfer.files);
        files.forEach(file => {
            const type = this.getFileType(file);
            if (type) {
                this.uploadFile(file, type);
            }
        });
    }

    getFileType(file) {
        const extension = file.name.split('.').pop().toLowerCase();
        if (extension === 'pdf') return 'pdf';
        if (['m4a', 'mp3', 'wav'].includes(extension)) return 'audio';
        if (extension === 'srt') return 'subs';
        if (['json', 'config'].includes(extension)) return 'config';
        if (['mp4', 'mov', 'avi', 'mkv'].includes(extension)) return 'video';
        return null;
    }

    async handleFileSelection(e) {
        const files = Array.from(e.target.files);

        for (const file of files) {
            const type = this.getFileType(file);
            if (type) {
                await this.uploadFile(file, type);
            }
        }

        e.target.value = ''; // Reset file input
    }

    async uploadFile(file, type) {
        console.log('=== 开始上传文件 ===');
        console.log('文件名:', file.name);
        console.log('文件类型:', type);
        console.log('文件大小:', file.size);
        
        const uploadArea = document.querySelector(`.upload-area[data-type="${type}"]`);
        console.log('获取到的uploadArea元素:', uploadArea);
        console.log('uploadArea.querySelector(.upload-info):', uploadArea ? uploadArea.querySelector('.upload-info') : null);
        
        uploadArea.classList.add('uploading');

        try {
            const formData = new FormData();
            formData.append('files', file);
            
            // 获取书名，如果没有提供则使用当前书名
            const bookName = this.getCurrentBookName();
            console.log('使用的书名:', bookName);
            formData.append('book_name', bookName);

            console.log('发送上传请求到 /api/upload');
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            console.log('上传响应状态:', response.status);
            console.log('上传响应数据:', data);

            if (response.ok) {
                console.log('=== 文件上传成功 ===');
                console.log('上传的文件信息:', data.files[type]);
                
                // 处理上传响应，将file_key映射为key字段
                const fileInfo = data.files[type];
                if (fileInfo && fileInfo.file_key) {
                    fileInfo.key = fileInfo.file_key;
                }
                
                this.uploadedFiles[type] = fileInfo;
                console.log('更新后的uploadedFiles:', this.uploadedFiles);
                this.updateUploadArea(uploadArea, type, file.name, true);
                
                // 更新已上传文件列表
                this.updateUploadedFilesList(type, file.name);
                
                // 设置默认输出文件名（仅在输出文件名为空时）
                this.setDefaultOutputNameIfNeeded();

                // If audio is uploaded, get duration and try to find matching subtitle file
                if (type === 'audio') {
                    console.log('=== 音频文件上传成功，开始处理音频相关逻辑 ===');
                    await this.getAudioDurationFromFile(file);
                    
                    // 显示字幕处理区域
                    this.showSubtitleSection();
                    
                    // 尝试查找并上传同名字幕文件
                    console.log('音频文件上传成功，开始查找同名字幕文件...');
                    // 使用后端返回的文件名，而不是原始文件名，确保文件名一致性
                    const audioFilename = fileInfo.name || file.name;
                    console.log('使用的音频文件名:', audioFilename);
                    await this.tryUploadMatchingSubtitle(audioFilename, bookName);
                    
                    // 尝试加载配置文件
                console.log('音频文件上传成功，开始检查配置文件...');
                const configExists = await this.loadConfigFileIfExists(bookName, false);
                
                // 如果配置文件存在，自动加载配置数据
                if (configExists) {
                    console.log('配置文件存在，开始自动加载配置数据');
                    this.addLogEntry('配置文件存在，开始自动加载配置数据', 'info');
                    
                    // 确保翻页时间设置部分是显示状态
                    if (this.pageTimingSection) {
                        this.pageTimingSection.style.display = 'block';
                        console.log('设置翻页时间设置部分为显示状态');
                    }
                    
                    // 延迟加载配置数据，确保DOM更新完成
                    setTimeout(async () => {
                        const loadSuccess = await this.loadPageTimingsData(false);
                        if (loadSuccess) {
                            console.log('配置数据已自动加载到表单');
                            this.addLogEntry('配置数据已自动加载到表单', 'success');
                        } else {
                            console.warn('配置数据自动加载未成功');
                            this.addLogEntry('配置数据自动加载未成功', 'warning');
                        }
                    }, 300);
                }
                }
                
                // If subtitle is uploaded, try to load config file
                if (type === 'subs') {
                    console.log('=== 字幕文件上传成功，开始处理字幕相关逻辑 ===');
                    
                    // 更新字幕文件选择框选项
                    this.updateSubtitleFileSelect(file.name);
                    
                    // 尝试加载配置文件
                console.log('字幕文件上传成功，开始检查配置文件...');
                const configExists = await this.loadConfigFileIfExists(bookName, false);
                
                // 如果配置文件存在，自动加载配置数据
                if (configExists) {
                    console.log('配置文件存在，开始自动加载配置数据');
                    this.addLogEntry('配置文件存在，开始自动加载配置数据', 'info');
                    
                    // 确保翻页时间设置部分是显示状态
                    if (this.pageTimingSection) {
                        this.pageTimingSection.style.display = 'block';
                        console.log('设置翻页时间设置部分为显示状态');
                    }
                    
                    // 延迟加载配置数据，确保DOM更新完成
                    setTimeout(async () => {
                        const loadSuccess = await this.loadPageTimingsData(false);
                        if (loadSuccess) {
                            console.log('配置数据已自动加载到表单');
                            this.addLogEntry('配置数据已自动加载到表单', 'success');
                        } else {
                            console.warn('配置数据自动加载未成功');
                            this.addLogEntry('配置数据自动加载未成功', 'warning');
                        }
                    }, 300);
                }
                }
                
                // If config is uploaded, load the config data
                if (type === 'config') {
                    console.log('=== 配置文件上传成功，开始处理配置相关逻辑 ===');
                    
                    // 确保翻页时间设置部分是显示状态
                    if (this.pageTimingSection) {
                        this.pageTimingSection.style.display = 'block';
                        console.log('设置翻页时间设置部分为显示状态');
                        console.log('pageTimingSection元素:', this.pageTimingSection);
                        console.log('pageTimingSection显示状态:', window.getComputedStyle(this.pageTimingSection).display);
                        this.addLogEntry('配置文件上传成功，设置翻页时间设置部分为显示状态', 'success');
                    } else {
                        console.error('pageTimingSection元素不存在');
                        this.addLogEntry('错误：pageTimingSection元素不存在', 'error');
                    }
                    
                    // 延迟加载配置数据，确保DOM更新完成
                    setTimeout(async () => {
                        try {
                            console.log('开始自动加载配置数据');
                            this.addLogEntry('开始自动加载配置数据', 'info');
                            
                            // 使用与手动加载配置相同的流程
                            const success = await this.loadPageTimingsData();
                            
                            if (success) {
                                console.log('配置数据已自动加载到表单');
                                this.addLogEntry('配置数据已自动加载到表单', 'success');
                                
                                // 再次确保翻页时间设置部分是显示状态
                                if (this.pageTimingSection) {
                                    this.pageTimingSection.style.display = 'block';
                                    console.log('再次设置翻页时间设置部分为显示状态');
                                    this.addLogEntry('再次确认翻页时间设置部分为显示状态', 'success');
                                }
                            } else {
                                console.warn('配置数据自动加载未成功');
                                this.addLogEntry('配置数据自动加载未成功，请手动点击"加载配置"按钮', 'warning');
                            }
                        } catch (error) {
                            console.error('自动加载配置数据失败:', error);
                            this.addLogEntry(`自动加载配置数据失败: ${error.message}，请手动点击"加载配置"按钮`, 'error');
                        }
                    }, 500); // 延迟500ms确保文件上传完全完成
                }

                // If all files are uploaded, show next section
                if (Object.keys(this.uploadedFiles).length === 3 || 
                    (this.uploadedFiles.pdf && this.uploadedFiles.audio && this.uploadedFiles.subs)) {
                    console.log('=== 所有文件已上传，进入下一步 ===');
                    this.showNextSection();
                    this.loadPDFInfo();
                }

                // 移除单个文件上传成功的提示
                // this.uploadStatus.textContent = `${file.name} 上传成功`;
                // this.uploadStatus.className = 'ms-3 text-success';
            } else {
                console.error('=== 文件上传失败 ===');
                console.error('错误信息:', data.error);
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('=== 上传过程发生异常 ===');
            console.error('异常详情:', error);
            this.updateUploadArea(uploadArea, type, file.name, false, error.message);
            this.showError(`上传失败: ${error.message}`);
        } finally {
            uploadArea.classList.remove('uploading');
        }
    }

    updateUploadArea(area, type, filename, success, error = null) {
        console.log('=== updateUploadArea 被调用 ===');
        console.log('area参数:', area);
        console.log('type参数:', type);
        console.log('filename参数:', filename);
        console.log('success参数:', success);
        
        const infoDiv = area.querySelector('.upload-info');
        console.log('获取到的infoDiv:', infoDiv);

        if (success) {
            area.classList.add('uploaded');
            area.classList.remove('error');
            
            // 如果是音频文件，添加悬浮预览功能
            if (type === 'audio') {
                console.log('=== 开始更新音频上传区域 ===');
                console.log('文件名:', filename);
                console.log('上传区域元素:', area);
                console.log('infoDiv元素:', infoDiv);
                
                // 检查是否已经设置了文件名显示，避免重复设置
                const existingContent = infoDiv.innerHTML;
                if (!existingContent.includes('text-success') || !existingContent.includes(filename)) {
                    // 添加悬浮预览功能
                    infoDiv.innerHTML = `
                        <div class="text-success small">
                            <span class="audio-upload-filename-hover" style="cursor: pointer;">${filename}</span>
                            <!-- 悬浮预览窗体 -->
                            <div class="audio-upload-hover-preview position-fixed top-0 start-0 mt-2 p-3 bg-white border rounded shadow" style="display: none; z-index: 100000 !important; width: 300px;">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <h6 class="mb-0">音频预览</h6>
                                    <div>
                                        <button class="audio-upload-pin-btn btn btn-sm btn-outline-secondary me-1" title="固定">
                                            <i class="bi bi-pin"></i>
                                        </button>
                                        <button class="audio-upload-close-btn btn btn-sm btn-outline-secondary" title="关闭">
                                            <i class="bi bi-x"></i>
                                        </button>
                                    </div>
                                </div>
                                <audio class="audio-upload-hover-player-element" controls style="width: 100%;"></audio>
                            </div>
                        </div>
                    `;
                    
                    // 为新添加的音频文件名绑定悬浮事件
                    const audioFilenameHover = infoDiv.querySelector('.audio-upload-filename-hover');
                    const audioHoverPreview = infoDiv.querySelector('.audio-upload-hover-preview');
                    const audioHoverPlayerElement = infoDiv.querySelector('.audio-upload-hover-player-element');
                    const audioPinBtn = infoDiv.querySelector('.audio-upload-pin-btn');
                    const audioCloseBtn = infoDiv.querySelector('.audio-upload-close-btn');
                    
                    if (audioFilenameHover && audioHoverPreview && audioHoverPlayerElement) {
                        let audioHoverPinned = false;
                        let audioHoverShowTimeout = null;
                        let audioHoverTimeout = null;
                        
                        audioFilenameHover.addEventListener('mouseenter', () => {
                            // 延迟0.5秒后显示悬浮预览
                            audioHoverShowTimeout = setTimeout(() => {
                                if (this.uploadedFiles.audio) {
                                    // 计算预览窗口位置
                                    const rect = audioFilenameHover.getBoundingClientRect();
                                    const previewWidth = 300;  // 预览窗口宽度
                                    
                                    // 计算水平位置，确保不超出屏幕右边界
                                    let leftPos = rect.left + window.scrollX;
                                    if (leftPos + previewWidth > window.innerWidth) {
                                        leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
                                    }
                                    
                                    // 计算垂直位置，优先显示在下方，如果空间不够则显示在上方
                                    let topPos;
                                    const spaceBelow = window.innerHeight - rect.bottom;
                                    const spaceAbove = rect.top;
                                    
                                    if (spaceBelow > 100) {  // 音频播放器高度较小
                                        // 下方空间足够，显示在下方
                                        topPos = rect.bottom + window.scrollY;
                                    } else if (spaceAbove > 100) {
                                        // 上方空间足够，显示在上方
                                        topPos = rect.top + window.scrollY - 100;
                                    } else {
                                        // 两处空间都不够，选择空间较大的一方
                                        if (spaceBelow >= spaceAbove) {
                                            topPos = rect.bottom + window.scrollY;
                                        } else {
                                            topPos = rect.top + window.scrollY - 100;
                                        }
                                    }
                                    
                                    // 应用计算的位置
                                    audioHoverPreview.style.top = topPos + 'px';
                                    audioHoverPreview.style.left = leftPos + 'px';
                                    
                                    // 显示悬浮预览
                                    audioHoverPreview.style.display = 'block';
                                    
                                    // 设置音频源并加载
                                    // 使用file_key构建正确的音频URL
                                    const audioUrl = `/api/audio-file/${this.uploadedFiles.audio.file_key}`;
                                    audioHoverPlayerElement.src = audioUrl;
                                    audioHoverPlayerElement.load();
                                }
                            }, 500);
                        });
                        
                        audioFilenameHover.addEventListener('mouseleave', () => {
                            // 清除显示定时器
                            clearTimeout(audioHoverShowTimeout);
                            
                            // 延迟隐藏，以便用户可以将鼠标移动到播放器上
                            setTimeout(() => {
                                // 只有在未固定且鼠标不在播放器上时才隐藏
                                if (!audioHoverPinned && !audioHoverPreview.matches(':hover')) {
                                    audioHoverTimeout = setTimeout(() => {
                                        // 暂停音频如果正在播放
                                        audioHoverPlayerElement.pause();
                                        
                                        // 隐藏悬浮预览
                                        audioHoverPreview.style.display = 'none';
                                    }, 100);
                                }
                            }, 300);
                        });
                        
                        audioHoverPreview.addEventListener('mouseenter', () => {
                            // 当鼠标进入播放器时，取消隐藏定时器
                            clearTimeout(audioHoverTimeout);
                        });
                        
                        audioHoverPreview.addEventListener('mouseleave', () => {
                            // 只有在未固定的情况下才隐藏
                            if (!audioHoverPinned) {
                                audioHoverTimeout = setTimeout(() => {
                                    // 暂停音频如果正在播放
                                    audioHoverPlayerElement.pause();
                                    
                                    // 隐藏悬浮预览
                                    audioHoverPreview.style.display = 'none';
                                }, 100);
                            }
                        });
                        
                        // 固定按钮点击事件
                        if (audioPinBtn) {
                            audioPinBtn.addEventListener('click', () => {
                                audioHoverPinned = !audioHoverPinned;
                                
                                // 更新固定按钮外观
                                if (audioHoverPinned) {
                                    audioPinBtn.classList.remove('btn-outline-secondary');
                                    audioPinBtn.classList.add('btn-primary');
                                    audioPinBtn.innerHTML = '<i class="bi bi-pin-fill"></i>';
                                    audioPinBtn.title = '取消固定';
                                } else {
                                    audioPinBtn.classList.remove('btn-primary');
                                    audioPinBtn.classList.add('btn-outline-secondary');
                                    audioPinBtn.innerHTML = '<i class="bi bi-pin"></i>';
                                    audioPinBtn.title = '固定';
                                }
                            });
                        }
                        
                        // 关闭按钮点击事件
                        if (audioCloseBtn) {
                            audioCloseBtn.addEventListener('click', () => {
                                // 暂停音频如果正在播放
                                audioHoverPlayerElement.pause();
                                
                                // 隐藏悬浮预览
                                audioHoverPreview.style.display = 'none';
                                
                                // 重置固定状态
                                if (audioHoverPinned) {
                                    audioHoverPinned = false;
                                    audioPinBtn.classList.remove('btn-primary');
                                    audioPinBtn.classList.add('btn-outline-secondary');
                                    audioPinBtn.innerHTML = '<i class="bi bi-pin"></i>';
                                    audioPinBtn.title = '固定';
                                }
                            });
                        }
                    }
                }
                
                console.log('音频上传区域已更新，文件名:', filename);
            } else if (type === 'subs') {
                // 检查是否已经设置了文件名显示，避免重复设置
                const existingContent = infoDiv.innerHTML;
                // 强制更新字幕文件信息，确保UI与数据同步
                if (!existingContent.includes('text-success') || !existingContent.includes(filename) || !this.uploadedFiles.subs) {
                    infoDiv.innerHTML = `
                        <div class="text-success small">
                            <span class="subs-upload-filename-hover" style="cursor: pointer;">${filename}</span>
                            <!-- 悬浮预览窗体 -->
                            <div class="subs-upload-hover-preview position-fixed top-0 start-0 mt-2 p-3 bg-white border rounded shadow" style="display: none; z-index: 100000 !important; max-width: 300px; max-height: 160px; overflow-y: auto;">
                                <div class="mb-2">
                                    <h6 class="mb-0">字幕预览</h6>
                                </div>
                                <div class="subs-upload-preview-content small"></div>
                            </div>
                        </div>
                    `;
                    
                    console.log('字幕上传区域已更新，文件名:', filename);
                    
                    // 为新添加的字幕文件名绑定悬浮事件
                    const subsFilenameHover = infoDiv.querySelector('.subs-upload-filename-hover');
                    const subsHoverPreview = infoDiv.querySelector('.subs-upload-hover-preview');
                    const subsPreviewContent = infoDiv.querySelector('.subs-upload-preview-content');

                    if (subsFilenameHover && subsHoverPreview && subsPreviewContent) {
                    let subsHoverTimeout = null;
                    let subsHoverShowTimeout = null;
                    
                    subsFilenameHover.addEventListener('mouseenter', () => {
                        console.log('=== 字幕悬浮事件被触发 ===');
                        // 延迟0.5秒后显示悬浮预览
                        subsHoverShowTimeout = setTimeout(() => {
                            console.log('=== 字幕悬浮预览定时器触发 ===');
                            if (this.uploadedFiles.subs) {
                                // 计算预览窗口位置
                                const rect = subsFilenameHover.getBoundingClientRect();
                                const previewWidth = 300;  // 预览窗口宽度（更新为CSS中设置的宽度）
                                
                                // 计算水平位置，确保不超出屏幕右边界
                                let leftPos = rect.left + window.scrollX;
                                if (leftPos + previewWidth > window.innerWidth) {
                                    leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
                                }
                                
                                // 计算垂直位置，优先显示在下方，如果空间不够则显示在上方
                                let topPos;
                                const spaceBelow = window.innerHeight - rect.bottom;
                                const spaceAbove = rect.top;
                                
                                if (spaceBelow > 200) {  // 字幕预览高度较小
                                    // 下方空间足够，显示在下方
                                    topPos = rect.bottom + window.scrollY;
                                } else if (spaceAbove > 200) {
                                    // 上方空间足够，显示在上方
                                    topPos = rect.top + window.scrollY - 200;
                                } else {
                                    // 两处空间都不够，选择空间较大的一方
                                    if (spaceBelow >= spaceAbove) {
                                        topPos = rect.bottom + window.scrollY;
                                    } else {
                                        topPos = rect.top + window.scrollY - 200;
                                    }
                                }
                                
                                // 应用计算的位置
                                subsHoverPreview.style.top = topPos + 'px';
                                subsHoverPreview.style.left = leftPos + 'px';
                                
                                // 显示悬浮预览
                                subsHoverPreview.style.display = 'block';
                                
                                // 加载字幕内容
                                const subtitleFilename = this.uploadedFiles.subs.filename || this.uploadedFiles.subs.name;
                                console.log('加载字幕内容:', subtitleFilename);
                                this.loadSubtitleContentForPreview(subtitleFilename, subsPreviewContent);
                            }
                        }, 500);
                    });
                    
                    subsFilenameHover.addEventListener('mouseleave', () => {
                        // 清除显示定时器
                        clearTimeout(subsHoverShowTimeout);

                        // 延迟隐藏，以便用户可以将鼠标移动到预览上
                        setTimeout(() => {
                            // 只有鼠标不在预览上时才隐藏
                            if (!subsHoverPreview.matches(':hover')) {
                                subsHoverTimeout = setTimeout(() => {
                                    // 隐藏悬浮预览
                                    subsHoverPreview.style.display = 'none';
                                }, 100);
                            }
                        }, 300);
                    });

                    subsHoverPreview.addEventListener('mouseenter', () => {
                        // 当鼠标进入预览时，取消隐藏定时器
                        clearTimeout(subsHoverTimeout);
                    });

                    subsHoverPreview.addEventListener('mouseleave', () => {
                        // 隐藏悬浮预览
                        subsHoverTimeout = setTimeout(() => {
                            subsHoverPreview.style.display = 'none';
                        }, 200);
                  });
                }
            }
            } else if (type === 'config') {
                infoDiv.innerHTML = `
                    <div class="text-success small">
                        <span class="config-upload-filename-hover" style="cursor: pointer;">${filename}</span>
                        <!-- 悬浮预览窗体 -->
                        <div class="config-upload-hover-preview position-fixed top-0 start-0 mt-2 p-3 bg-white border rounded shadow" style="display: none; z-index: 100000 !important; width: 400px; max-height: 300px; overflow-y: auto;">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6 class="mb-0">配置预览</h6>
                                <div>
                                    <button class="config-upload-pin-btn btn btn-sm btn-outline-secondary me-1" title="固定">
                                        <i class="bi bi-pin"></i>
                                    </button>
                                    <button class="config-upload-close-btn btn btn-sm btn-outline-secondary" title="关闭">
                                        <i class="bi bi-x"></i>
                                    </button>
                                </div>
                            </div>
                            <div class="config-upload-preview-content small">加载中...</div>
                        </div>
                    </div>
                `;
                
                // 配置文件上传成功后，使用轮询机制确保配置文件已完全处理
                this.pollForConfigAvailability(bookName || this.getCurrentBookName(), 0, 5);
                
                // 为新添加的配置文件名绑定悬浮事件
                const configFilenameHover = infoDiv.querySelector('.config-upload-filename-hover');
                const configHoverPreview = infoDiv.querySelector('.config-upload-hover-preview');
                const configPreviewContent = infoDiv.querySelector('.config-upload-preview-content');
                const configPinBtn = infoDiv.querySelector('.config-upload-pin-btn');
                const configCloseBtn = infoDiv.querySelector('.config-upload-close-btn');
                
                if (configFilenameHover && configHoverPreview && configPreviewContent) {
                    let configHoverPinned = false;
                    let configHoverShowTimeout = null;
                    let configHoverTimeout = null;
                    
                    configFilenameHover.addEventListener('mouseenter', () => {
                        // 延迟0.5秒后显示悬浮预览
                        configHoverShowTimeout = setTimeout(() => {
                            if (this.uploadedFiles.config) {
                                // 计算预览窗口位置
                                const rect = configFilenameHover.getBoundingClientRect();
                                const previewWidth = 400;  // 预览窗口宽度
                                
                                // 计算水平位置，确保不超出屏幕右边界
                                let leftPos = rect.left + window.scrollX;
                                if (leftPos + previewWidth > window.innerWidth) {
                                    leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
                                }
                                
                                // 计算垂直位置，优先显示在下方，如果空间不够则显示在上方
                                let topPos;
                                const spaceBelow = window.innerHeight - rect.bottom;
                                const spaceAbove = rect.top;
                                
                                if (spaceBelow > 200) {  // 配置预览高度较小
                                    // 下方空间足够，显示在下方
                                    topPos = rect.bottom + window.scrollY;
                                } else if (spaceAbove > 200) {
                                    // 上方空间足够，显示在上方
                                    topPos = rect.top + window.scrollY - 200;
                                } else {
                                    // 两处空间都不够，选择空间较大的一方
                                    if (spaceBelow >= spaceAbove) {
                                        topPos = rect.bottom + window.scrollY;
                                    } else {
                                        topPos = rect.top + window.scrollY - 200;
                                    }
                                }
                                
                                // 应用计算的位置
                                configHoverPreview.style.top = topPos + 'px';
                                configHoverPreview.style.left = leftPos + 'px';
                                
                                // 显示悬浮预览
                                configHoverPreview.style.display = 'block';
                                
                                // 加载配置内容
                                this.loadConfigContentForUpload(configPreviewContent);
                            }
                        }, 500);
                    });
                    
                    configFilenameHover.addEventListener('mouseleave', () => {
                        // 清除显示定时器
                        clearTimeout(configHoverShowTimeout);
                        
                        // 延迟隐藏，以便用户可以将鼠标移动到预览上
                        setTimeout(() => {
                            // 只有在未固定且鼠标不在预览上时才隐藏
                            if (!configHoverPinned && !configHoverPreview.matches(':hover')) {
                                configHoverTimeout = setTimeout(() => {
                                    // 隐藏悬浮预览
                                    configHoverPreview.style.display = 'none';
                                }, 100);
                            }
                        }, 300);
                    });
                    
                    configHoverPreview.addEventListener('mouseenter', () => {
                        // 当鼠标进入预览时，取消隐藏定时器
                        clearTimeout(configHoverTimeout);
                    });
                    
                    configHoverPreview.addEventListener('mouseleave', () => {
                        // 只有在未固定的情况下才隐藏
                        if (!configHoverPinned) {
                            configHoverTimeout = setTimeout(() => {
                                // 隐藏悬浮预览
                                configHoverPreview.style.display = 'none';
                            }, 100);
                        }
                    });
                    
                    // 固定按钮点击事件
                    if (configPinBtn) {
                        configPinBtn.addEventListener('click', () => {
                            configHoverPinned = !configHoverPinned;
                            
                            // 更新固定按钮外观
                            if (configHoverPinned) {
                                configPinBtn.classList.remove('btn-outline-secondary');
                                configPinBtn.classList.add('btn-primary');
                                configPinBtn.innerHTML = '<i class="bi bi-pin-fill"></i>';
                                configPinBtn.title = '取消固定';
                            } else {
                                configPinBtn.classList.remove('btn-primary');
                                configPinBtn.classList.add('btn-outline-secondary');
                                configPinBtn.innerHTML = '<i class="bi bi-pin"></i>';
                                configPinBtn.title = '固定';
                            }
                        });
                    }
                    
                    // 关闭按钮点击事件
                    if (configCloseBtn) {
                        configCloseBtn.addEventListener('click', () => {
                            // 隐藏悬浮预览
                            configHoverPreview.style.display = 'none';
                            
                            // 重置固定状态
                            if (configHoverPinned) {
                                configHoverPinned = false;
                                configPinBtn.classList.remove('btn-primary');
                                configPinBtn.classList.add('btn-outline-secondary');
                                configPinBtn.innerHTML = '<i class="bi bi-pin"></i>';
                                configPinBtn.title = '固定';
                            }
                        });
                    }
                }
            } else if (type === 'video') {
                infoDiv.innerHTML = `
                    <div class="text-success small">
                        <span class="video-upload-filename-hover" style="cursor: pointer;">${filename}</span>
                        <!-- 悬浮预览窗体 -->
                        <div class="video-upload-hover-preview position-fixed top-0 start-0 mt-2 p-3 bg-white border rounded shadow" style="display: none; z-index: 100000 !important; width: 400px;">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6 class="mb-0">视频预览</h6>
                                <div>
                                    <button class="video-upload-pin-btn btn btn-sm btn-outline-secondary me-1" title="固定">
                                        <i class="bi bi-pin"></i>
                                    </button>
                                    <button class="video-upload-close-btn btn btn-sm btn-outline-secondary" title="关闭">
                                        <i class="bi bi-x"></i>
                                    </button>
                                </div>
                            </div>
                            <video class="video-upload-hover-player-element" controls style="width: 100%;"></video>
                        </div>
                    </div>
                `;
                
                // 为新添加的视频文件名绑定悬浮事件
                const videoFilenameHover = infoDiv.querySelector('.video-upload-filename-hover');
                const videoHoverPreview = infoDiv.querySelector('.video-upload-hover-preview');
                const videoHoverPlayerElement = infoDiv.querySelector('.video-upload-hover-player-element');
                const videoPinBtn = infoDiv.querySelector('.video-upload-pin-btn');
                const videoCloseBtn = infoDiv.querySelector('.video-upload-close-btn');
                
                if (videoFilenameHover && videoHoverPreview && videoHoverPlayerElement) {
                    let videoHoverPinned = false;
                    let videoHoverShowTimeout = null;
                    let videoHoverTimeout = null;
                    
                    videoFilenameHover.addEventListener('mouseenter', () => {
                        // 延迟0.5秒后显示悬浮预览
                        videoHoverShowTimeout = setTimeout(() => {
                            if (this.uploadedFiles.video) {
                                // 计算预览窗口位置
                                const rect = videoFilenameHover.getBoundingClientRect();
                                const previewWidth = 400;  // 预览窗口宽度
                                
                                // 计算水平位置，确保不超出屏幕右边界
                                let leftPos = rect.left + window.scrollX;
                                if (leftPos + previewWidth > window.innerWidth) {
                                    leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
                                }
                                
                                // 计算垂直位置，优先显示在下方，如果空间不够则显示在上方
                                let topPos;
                                const spaceBelow = window.innerHeight - rect.bottom;
                                const spaceAbove = rect.top;
                                
                                if (spaceBelow > 250) {  // 视频播放器高度较大
                                    // 下方空间足够，显示在下方
                                    topPos = rect.bottom + window.scrollY;
                                } else if (spaceAbove > 250) {
                                    // 上方空间足够，显示在上方
                                    topPos = rect.top + window.scrollY - 250;
                                } else {
                                    // 两处空间都不够，选择空间较大的一方
                                    if (spaceBelow >= spaceAbove) {
                                        topPos = rect.bottom + window.scrollY;
                                    } else {
                                        topPos = rect.top + window.scrollY - 250;
                                    }
                                }
                                
                                // 应用计算的位置
                                videoHoverPreview.style.top = topPos + 'px';
                                videoHoverPreview.style.left = leftPos + 'px';
                                
                                // 显示悬浮预览
                                videoHoverPreview.style.display = 'block';
                                
                                // 设置视频源
                                videoHoverPlayerElement.src = this.uploadedFiles.video.url;
                            }
                        }, 500);
                    });
                    
                    videoFilenameHover.addEventListener('mouseleave', () => {
                        // 清除显示定时器
                        clearTimeout(videoHoverShowTimeout);
                        
                        // 延迟隐藏，以便用户可以将鼠标移动到播放器上
                        setTimeout(() => {
                            // 只有在未固定且鼠标不在播放器上时才隐藏
                            if (!videoHoverPinned && !videoHoverPreview.matches(':hover')) {
                                videoHoverTimeout = setTimeout(() => {
                                    // 暂停视频如果正在播放
                                    videoHoverPlayerElement.pause();
                                    
                                    // 隐藏悬浮预览
                                    videoHoverPreview.style.display = 'none';
                                }, 100);
                            }
                        }, 300);
                    });
                    
                    videoHoverPreview.addEventListener('mouseenter', () => {
                        // 当鼠标进入播放器时，取消隐藏定时器
                        clearTimeout(videoHoverTimeout);
                    });
                    
                    videoHoverPreview.addEventListener('mouseleave', () => {
                        // 只有在未固定的情况下才隐藏
                        if (!videoHoverPinned) {
                            videoHoverTimeout = setTimeout(() => {
                                // 暂停视频如果正在播放
                                videoHoverPlayerElement.pause();
                                
                                // 隐藏悬浮预览
                                videoHoverPreview.style.display = 'none';
                            }, 100);
                        }
                    });
                    
                    // 固定按钮点击事件
                    if (videoPinBtn) {
                        videoPinBtn.addEventListener('click', () => {
                            videoHoverPinned = !videoHoverPinned;
                            
                            // 更新固定按钮外观
                            if (videoHoverPinned) {
                                videoPinBtn.classList.remove('btn-outline-secondary');
                                videoPinBtn.classList.add('btn-primary');
                                videoPinBtn.innerHTML = '<i class="bi bi-pin-fill"></i>';
                                videoPinBtn.title = '取消固定';
                            } else {
                                videoPinBtn.classList.remove('btn-primary');
                                videoPinBtn.classList.add('btn-outline-secondary');
                                videoPinBtn.innerHTML = '<i class="bi bi-pin"></i>';
                                videoPinBtn.title = '固定';
                            }
                        });
                    }
                    
                    // 关闭按钮点击事件
                    if (videoCloseBtn) {
                        videoCloseBtn.addEventListener('click', () => {
                            // 暂停视频如果正在播放
                            videoHoverPlayerElement.pause();
                            
                            // 隐藏悬浮预览
                            videoHoverPreview.style.display = 'none';
                            
                            // 重置固定状态
                            if (videoHoverPinned) {
                                videoHoverPinned = false;
                                videoPinBtn.classList.remove('btn-primary');
                                videoPinBtn.classList.add('btn-outline-secondary');
                                videoPinBtn.innerHTML = '<i class="bi bi-pin"></i>';
                                videoPinBtn.title = '固定';
                            }
                        });
                    }
                }
            } else if (type === 'pdf') {
                infoDiv.innerHTML = `
                    <div class="text-success small">
                        <span class="pdf-upload-filename-hover" style="cursor: pointer;">${filename}</span>
                        <!-- 悬浮预览窗体 -->
                        <div class="pdf-upload-hover-preview position-fixed top-0 start-0 mt-2 p-3 bg-white border rounded shadow" style="display: none; z-index: 100000 !important; width: 400px; height: 250px;">
                            <iframe class="pdf-upload-hover-preview-element" style="width: 100%; height: 100%; border: none;"></iframe>
                        </div>
                    </div>
                `;
                
                // 为新添加的PDF文件名绑定悬浮事件
                const pdfFilenameHover = infoDiv.querySelector('.pdf-upload-filename-hover');
                const pdfHoverPreview = infoDiv.querySelector('.pdf-upload-hover-preview');
                const pdfHoverPreviewElement = infoDiv.querySelector('.pdf-upload-hover-preview-element');
                
                if (pdfFilenameHover && pdfHoverPreview && pdfHoverPreviewElement) {
                    let pdfHoverShowTimeout = null;
                    let pdfHoverTimeout = null;
                    
                    pdfFilenameHover.addEventListener('mouseenter', () => {
                        // 延迟0.5秒后显示悬浮预览
                        pdfHoverShowTimeout = setTimeout(() => {
                            if (this.uploadedFiles.pdf) {
                                // 计算预览窗口位置
                                const rect = pdfFilenameHover.getBoundingClientRect();
                                const previewWidth = 400;  // 预览窗口宽度
                                const previewHeight = 250; // 预览窗口高度
                                
                                // 计算水平位置，确保不超出屏幕右边界
                                let leftPos = rect.left + window.scrollX;
                                if (leftPos + previewWidth > window.innerWidth) {
                                    leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
                                }
                                
                                // 计算垂直位置，优先显示在下方，如果空间不够则显示在上方
                                let topPos;
                                const spaceBelow = window.innerHeight - rect.bottom;
                                const spaceAbove = rect.top;
                                
                                if (spaceBelow > previewHeight + 10) {
                                    // 下方空间足够，显示在下方
                                    topPos = rect.bottom + window.scrollY;
                                } else if (spaceAbove > previewHeight + 10) {
                                    // 上方空间足够，显示在上方
                                    topPos = rect.top + window.scrollY - previewHeight;
                                } else {
                                    // 两处空间都不够，选择空间较大的一方
                                    if (spaceBelow >= spaceAbove) {
                                        topPos = rect.bottom + window.scrollY;
                                    } else {
                                        topPos = rect.top + window.scrollY - previewHeight;
                                    }
                                }
                                
                                // 应用计算的位置
                                pdfHoverPreview.style.top = topPos + 'px';
                                pdfHoverPreview.style.left = leftPos + 'px';
                                
                                // 显示悬浮预览
                                pdfHoverPreview.style.display = 'block';
                                
                                // 设置PDF源，添加参数以隐藏PDF查看器的工具栏
                                const bookName = this.getCurrentBookName();
                                const pdfFilename = this.uploadedFiles.pdf.name || this.uploadedFiles.pdf.filename;
                                pdfHoverPreviewElement.src = `/api/pdf-preview/${bookName}/${pdfFilename}#toolbar=0&navpanes=0&scrollbar=0`;
                            }
                        }, 500);
                    });
                    
                    pdfFilenameHover.addEventListener('mouseleave', () => {
                        // 清除显示定时器
                        clearTimeout(pdfHoverShowTimeout);
                        
                        // 延迟隐藏，以便用户可以将鼠标移动到预览上
                        setTimeout(() => {
                            if (!pdfHoverPreview.matches(':hover')) {
                                pdfHoverTimeout = setTimeout(() => {
                                    // 隐藏悬浮预览
                                    pdfHoverPreview.style.display = 'none';
                                }, 100);
                            }
                        }, 300);
                    });
                    
                    pdfHoverPreview.addEventListener('mouseenter', () => {
                        // 当鼠标进入预览时，取消隐藏定时器
                        clearTimeout(pdfHoverTimeout);
                    });
                    
                    pdfHoverPreview.addEventListener('mouseleave', () => {
                        // 设置定时器隐藏预览
                        pdfHoverTimeout = setTimeout(() => {
                            pdfHoverPreview.style.display = 'none';
                        }, 100);
                    });
                }
            } else {
                infoDiv.innerHTML = `
                    <div class="text-success small">
                        ${filename}
                    </div>
                `;
            }
            
            // 更新已上传文件列表
            this.updateUploadedFilesList(type, filename);
            
            // 如果是配置文件，更新配置上传区域显示
            if (type === 'config' && this.configUploadArea) {
                const configInfoDiv = this.configUploadArea.querySelector('.upload-info');
                configInfoDiv.innerHTML = `
                    <div class="text-success small">
                        ${filename}
                    </div>
                `;
                this.configUploadArea.classList.add('uploaded');
            }
            
            // 如果是视频文件，更新视频上传区域显示
            if (type === 'video' && this.videoUploadArea) {
                const videoInfoDiv = this.videoUploadArea.querySelector('.upload-info');
                videoInfoDiv.innerHTML = `
                    <div class="text-success small">
                        ${filename}
                    </div>
                `;
                this.videoUploadArea.classList.add('uploaded');
            }
        } else {
            area.classList.add('error');
            area.classList.remove('uploaded');
            infoDiv.innerHTML = `
                <div class="text-danger small">
                    <i class="bi bi-x-circle"></i> ${error}
                </div>
            `;
        }
    }

    updateUploadedFilesList(type, filename) {
        // REMOVED - File info list has been removed from the page
        return;
        // 显示已上传文件列表区域
        const uploadedFilesList = document.getElementById('uploaded-files-list');
        if (!uploadedFilesList) return;
        uploadedFilesList.style.display = 'block';
        
        // 更新对应类型的文件项
        const fileItem = document.getElementById(`${type}-file-item`);
        const fileNameElement = document.getElementById(`${type}-file-name`);
        
        if (fileItem && fileNameElement) {
            fileItem.style.display = 'flex';
            fileNameElement.textContent = filename;
        }
        
        // 添加调试日志
        console.log(`更新${type}文件列表:`, filename);
        if (this.uploadedFiles[type]) {
            console.log(`${type}文件信息:`, this.uploadedFiles[type]);
            console.log(`${type}文件书名:`, this.uploadedFiles[type].book_name);
        }
        
        // 如果是音频文件，不再显示音频播放器，改为悬浮播放
        if (type === 'audio') {
            // 设置音频源（悬浮播放器会在鼠标悬浮时自动设置）
            console.log('音频文件已上传，可通过鼠标悬浮到文件名上进行预览');
            
            // 更新音频上传区域显示 - 确保文件名正确显示
            const audioUploadArea = document.querySelector('[data-type="audio"]');
            if (audioUploadArea) {
                const audioInfoDiv = audioUploadArea.querySelector('.upload-info');
                if (audioInfoDiv) {
                    // 检查是否已经设置了文件名显示
                    const existingContent = audioInfoDiv.innerHTML;
                    // 检查是否已经包含文件名显示，避免重复设置
                    if (!existingContent.includes('text-success') || !existingContent.includes(filename)) {
                        audioInfoDiv.innerHTML = `
                            <div class="text-success small" style="display: block !important; visibility: visible !important; opacity: 1 !important; color: green !important; font-weight: bold !important;">
                                ${filename}
                            </div>
                        `;
                    }
                }
                audioUploadArea.classList.add('uploaded');
            }
            
            // 重新获取音频文件名元素并绑定悬浮事件
            const audioFilenameElement = document.getElementById('audio-file-name');
            if (audioFilenameElement) {
                // 移除旧的事件监听器（通过克隆节点）
                const newAudioFilenameElement = audioFilenameElement.cloneNode(true);
                audioFilenameElement.parentNode.replaceChild(newAudioFilenameElement, audioFilenameElement);
                
                // 绑定新的事件监听器
                newAudioFilenameElement.addEventListener('mouseenter', () => {
                    console.log('鼠标进入音频文件名');
                    // 延迟0.5秒后显示悬浮预览
                    this.audioHoverShowTimeout = setTimeout(() => {
                        this.showAudioHoverPlayer();
                    }, 500);
                });
                
                newAudioFilenameElement.addEventListener('mouseleave', () => {
                    console.log('鼠标离开音频文件名');
                    // 清除显示定时器
                    clearTimeout(this.audioHoverShowTimeout);
                    
                    // 延迟隐藏，以便用户可以将鼠标移动到播放器上
                    setTimeout(() => {
                        // 只有在未固定且鼠标不在播放器上时才隐藏
                        if (!this.audioHoverPinned && !this.audioHoverPlayer.matches(':hover')) {
                            this.hideAudioHoverPlayer();
                        }
                    }, 300);
                });
                
                // 更新this.audioFilenameHover引用
                this.audioFilenameHover = newAudioFilenameElement;
            }
        }
        
        // 如果是视频文件，尝试获取视频信息
        if (type === 'video' && this.uploadedFiles[type]) {
            console.log('视频文件已上传，尝试获取视频信息...');
            this.checkExistingVideo();
        }
        
        // 设置默认输出文件名（仅在输出文件名为空时）
        this.setDefaultOutputNameIfNeeded();
        
        // 如果上传的是字幕文件，显示校验区域
        if (type === 'subs' && success) {
            console.log('=== 尝试显示字幕校验区域 ===');
            console.log('type:', type);
            console.log('success:', success);
            const validationSection = document.getElementById('subtitle-validation-section');
            console.log('validationSection元素:', validationSection);
            if (validationSection) {
                validationSection.style.display = 'block';
                console.log('✅ 字幕校验区域已显示');
            } else {
                console.error('❌ 找不到subtitle-validation-section元素');
            }
        }
        
        // 如果所有必需文件都已上传，检查配置文件
        if (this.uploadedFiles.pdf && this.uploadedFiles.audio && this.uploadedFiles.subs) {
            console.log('所有必需文件已上传，检查配置文件');
            // 延迟执行checkAndLoadConfigFile，避免在文件上传过程中立即触发
            setTimeout(() => {
                this.checkAndLoadConfigFile();
            }, 500);
        }
    }

    // 设置默认输出文件名
    setDefaultOutputName() {
        // 优先使用字幕文件名，其次使用音频文件名
        let baseName = '';
        if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
            const subsFileName = this.uploadedFiles.subs.name;
            const lastDotIndex = subsFileName.lastIndexOf('.');
            // 确保文件名不为空且不是以点开头
            if (lastDotIndex > 0) {
                baseName = subsFileName.substring(0, lastDotIndex);
            } else {
                baseName = subsFileName;
            }
        } else if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
            const audioFileName = this.uploadedFiles.audio.name;
            const lastDotIndex = audioFileName.lastIndexOf('.');
            // 确保文件名不为空且不是以点开头
            if (lastDotIndex > 0) {
                baseName = audioFileName.substring(0, lastDotIndex);
            } else {
                baseName = audioFileName;
            }
        }
        
        if (baseName) {
            // 更新主输出文件名字段
            if (this.outputName) {
                this.outputName.value = baseName;
            }
            
            // 同时更新自定义输出文件名字段
            const customOutputName = document.getElementById('output-name-custom');
            if (customOutputName) {
                customOutputName.value = baseName;
            }
        }
    }

    // 更新字幕文件选择框选项
    updateSubtitleFileSelect(filename) {
        if (!this.subtitleFileSelect) {
            console.error('字幕文件选择框元素不存在');
            return;
        }
        
        // 检查是否已存在该文件名的选项
        let optionExists = false;
        for (let i = 0; i < this.subtitleFileSelect.options.length; i++) {
            if (this.subtitleFileSelect.options[i].value === filename) {
                optionExists = true;
                // 如果已存在，选择该选项
                this.subtitleFileSelect.selectedIndex = i;
                break;
            }
        }
        
        // 如果选项不存在，则添加新选项
        if (!optionExists) {
            const newOption = document.createElement('option');
            newOption.value = filename;
            newOption.textContent = filename;
            newOption.selected = true; // 默认选择新上传的字幕文件
            this.subtitleFileSelect.appendChild(newOption);
            console.log(`字幕文件选择框已添加新选项: ${filename}`);
        } else {
            console.log(`字幕文件选择框已存在选项: ${filename}，已选择该选项`);
        }
        
        this.addLogEntry(`字幕文件选择框已更新: ${filename}`, 'success');
    }

    // 仅在输出文件名为空时设置默认输出文件名
    setDefaultOutputNameIfNeeded() {
        // 检查主输出文件名字段是否为空
        const isMainOutputNameEmpty = this.outputName && (!this.outputName.value || this.outputName.value.trim() === '');
        
        // 检查自定义输出文件名字段是否为空
        const customOutputName = document.getElementById('output-name-custom');
        const isCustomOutputNameEmpty = customOutputName && (!customOutputName.value || customOutputName.value.trim() === '');
        
        // 只有在两个字段都为空时才设置默认值
        if (isMainOutputNameEmpty && isCustomOutputNameEmpty) {
            this.setDefaultOutputName();
        }
    }

    // 统一的配置文件加载方法
    async loadConfigFileIfExists(bookName, showUserMessage = true) {
        try {
            // 配置文件名统一为config.json
            const actualConfigFilename = 'config.json';
            
            // 添加日志：开始加载配置
            console.log('=== loadConfigFileIfExists 被调用 ===');
            console.log('书名:', bookName);
            console.log('showUserMessage:', showUserMessage);
            console.log('当前uploadedFiles.config:', this.uploadedFiles.config);
            this.addLogEntry(`开始加载配置: ${bookName}`);
            
            // 检查是否已经从checkExistingFiles方法中加载了配置文件
            if (this.uploadedFiles.config && this.uploadedFiles.config.path) {
                console.log('配置文件已从checkExistingFiles方法中加载');
                this.addLogEntry('配置文件已从checkExistingFiles方法中加载');
                
                // 更新配置上传区域显示
                if (this.configUploadArea) {
                    const configInfoDiv = this.configUploadArea.querySelector('.upload-info');
                    configInfoDiv.innerHTML = `
                        <div class="text-success small">
                            ${this.uploadedFiles.config.name}
                        </div>
                    `;
                    this.configUploadArea.classList.add('uploaded');
                }
                
                // 自动加载配置信息到表单
                console.log('自动检测到配置文件存在，自动加载配置信息');
                this.addLogEntry('自动检测到配置文件存在，开始加载配置信息');
                
                // 加载配置数据
                try {
                    // 添加日志：开始加载配置数据
                    this.addLogEntry(`正在加载配置数据: ${this.uploadedFiles.config.path}`);
                    
                    const configResponse = await fetch(`/api/load-config/${encodeURIComponent(bookName)}`);
                    const configResult = await configResponse.json();
                    
                    if (configResponse.ok && configResult.status === 'success' && configResult.config_data) {
                        // 添加日志：配置文件检测成功
                        this.addLogEntry('配置文件检测成功');
                        console.log('配置文件已检测到，等待调用者加载配置数据');
                        
                        // 显示成功提示
                        if (showUserMessage) {
                            this.showSuccess(`自动检测到配置文件: ${this.uploadedFiles.config.name}`);
                        }
                        
                        return true; // 表示成功检测到配置文件
                    } else {
                        console.error('配置文件检测失败:', configResult);
                        this.addLogEntry(`配置文件检测失败: ${configResult.error || configResult.message}`);
                        return false;
                    }
                } catch (error) {
                    console.error('加载配置数据失败:', error);
                    this.addLogEntry(`加载配置数据失败: ${error.message}`);
                    this.showError('加载配置数据失败');
                }
                
                return false;
            }
            
            // 如果配置文件尚未加载，检查配置文件是否存在
            const response = await fetch(`/api/check-file-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(actualConfigFilename)}/config`);
            const data = await response.json();
            
            if (response.ok && data.exists) {
                // 添加日志：找到配置文件
                this.addLogEntry(`找到配置文件: ${data.path}`);
                
                // 配置文件存在，添加到已上传文件列表
                this.uploadedFiles.config = {
                    name: actualConfigFilename,
                    filename: actualConfigFilename,
                    path: data.path,
                    url: `/api/load-config/${encodeURIComponent(bookName)}?subtitle_filename=${encodeURIComponent(actualConfigFilename.replace('.json', ''))}`
                };
                
                // 更新配置文件显示 - REMOVED
                // const configItem = document.getElementById('config-file-item');
                // const configNameElement = document.getElementById('config-file-name');
                // 
                // if (configItem && configNameElement) {
                //     configItem.style.display = 'flex';
                //     configNameElement.textContent = actualConfigFilename;
                // }
                
                // 更新配置上传区域显示
                if (this.configUploadArea) {
                    const configInfoDiv = this.configUploadArea.querySelector('.upload-info');
                    configInfoDiv.innerHTML = `
                        <div class="text-success small">
                            ${actualConfigFilename}
                        </div>
                    `;
                    this.configUploadArea.classList.add('uploaded');
                }
                
                // 自动加载配置信息到表单
                console.log('自动检测到配置文件存在，自动加载配置信息');
                this.addLogEntry('自动检测到配置文件存在，开始加载配置信息');
                
                // 加载配置数据
                try {
                    // 添加日志：开始加载配置数据
                    this.addLogEntry(`正在加载配置数据: ${this.uploadedFiles.config.url}`);
                    
                    const configResponse = await fetch(this.uploadedFiles.config.url);
                    const configResult = await configResponse.json();
                    
                    if (configResponse.ok && configResult.status === 'success' && configResult.config_data) {
                        // 添加日志：配置文件检测成功
                        this.addLogEntry('配置文件检测成功');
                        console.log('配置文件已检测到，等待调用者加载配置数据');
                        
                        // 显示成功提示
                        if (showUserMessage) {
                            this.showSuccess(`自动检测到配置文件: ${actualConfigFilename}`);
                        }
                        
                        return true; // 表示成功检测到配置文件
                    } else {
                        console.error('配置文件检测失败:', configResult);
                        this.addLogEntry(`配置文件检测失败: ${configResult.error || configResult.message}`);
                        return false;
                    }
                } catch (error) {
                    console.error('加载配置数据失败:', error);
                    this.addLogEntry(`加载配置数据失败: ${error.message}`);
                    this.showError('加载配置数据失败');
                }
            } else {
                console.log('未找到配置文件，等待用户上传');
                this.addLogEntry('未找到配置文件，等待用户上传');
            }
            
            return false; // 表示未找到或加载失败
        } catch (error) {
            console.error('检查配置文件失败:', error);
            this.addLogEntry(`检查配置文件失败: ${error.message}`);
            return false;
        }
    }

    // 检查是否有上传的文件
    hasUploadedFiles() {
        // 检查是否有任何类型的文件已上传
        return !!(this.uploadedFiles.pdf || 
                 this.uploadedFiles.audio || 
                 this.uploadedFiles.subs || 
                 this.uploadedFiles.config || 
                 this.uploadedFiles.video);
    }

    // 检查服务器上是否有已上传的文件
    async checkExistingFiles() {
        try {
            console.log('检查服务器上是否有已上传的文件...');
            
            // 获取当前书名
            const bookName = this.getCurrentBookName();
            if (!bookName) {
                console.log('无法获取书名，跳过文件检查');
                return;
            }
            
            // 添加超时控制
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时
            
            // 获取服务器上的文件列表
            const response = await fetch('/api/get-uploaded-files', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ book_name: bookName }),
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            const data = await response.json();
            
            if (response.ok) {
                console.log('服务器上的文件列表:', data);
                
                // 恢复已上传的文件信息
                if (data.pdf) {
                    this.uploadedFiles.pdf = data.pdf;
                    console.log('恢复PDF文件信息:', this.uploadedFiles.pdf);
                    this.updateUploadArea(this.uploadAreas[0], 'pdf', data.pdf.name, true);
                }
                
                if (data.audio) {
                    this.uploadedFiles.audio = data.audio;
                    console.log('恢复音频文件信息:', this.uploadedFiles.audio);
                    this.updateUploadArea(this.uploadAreas[1], 'audio', data.audio.name, true);
                    // 确保音频文件名正确显示
                    const audioUploadArea = this.uploadAreas[1];
                    if (audioUploadArea) {
                        const audioInfoDiv = audioUploadArea.querySelector('.upload-info');
                        if (audioInfoDiv) {
                            // 检查是否已经设置了文件名显示，避免重复设置
                            const existingContent = audioInfoDiv.innerHTML;
                            if (!existingContent.includes('text-success') || !existingContent.includes(data.audio.name)) {
                                audioInfoDiv.innerHTML = `
                                    <div class="text-success small" style="display: block !important; visibility: visible !important; opacity: 1 !important; color: green !important; font-weight: bold !important;">
                                        ${data.audio.name}
                                    </div>
                                `;
                            }
                        }
                    }
                    
                    // 重新获取音频文件名元素并绑定悬浮事件
                    const audioFilenameElement = document.getElementById('audio-file-name');
                    if (audioFilenameElement) {
                        // 移除旧的事件监听器（通过克隆节点）
                        const newAudioFilenameElement = audioFilenameElement.cloneNode(true);
                        audioFilenameElement.parentNode.replaceChild(newAudioFilenameElement, audioFilenameElement);
                        
                        // 绑定新的事件监听器
                        newAudioFilenameElement.addEventListener('mouseenter', () => {
                            console.log('鼠标进入音频文件名');
                            // 延迟0.5秒后显示悬浮预览
                            this.audioHoverShowTimeout = setTimeout(() => {
                                this.showAudioHoverPlayer();
                            }, 500);
                        });
                        
                        newAudioFilenameElement.addEventListener('mouseleave', () => {
                            console.log('鼠标离开音频文件名');
                            // 清除显示定时器
                            clearTimeout(this.audioHoverShowTimeout);
                            
                            // 延迟隐藏，以便用户可以将鼠标移动到播放器上
                            setTimeout(() => {
                                // 只有在未固定且鼠标不在播放器上时才隐藏
                                if (!this.audioHoverPinned && !this.audioHoverPlayer.matches(':hover')) {
                                    this.hideAudioHoverPlayer();
                                }
                            }, 300);
                        });
                        
                        // 更新this.audioFilenameHover引用
                        this.audioFilenameHover = newAudioFilenameElement;
                    }
                }
                
                if (data.subs) {
                    this.uploadedFiles.subs = {
                        name: data.subs.name,
                        filename: data.subs.filename || data.subs.name,
                        path: data.subs.path,
                        size: data.subs.size,
                        url: data.subs.url,
                        book_name: data.subs.book_name,
                        key: data.subs.key,
                        file_key: data.subs.file_key
                    };
                    console.log('恢复字幕文件信息:', this.uploadedFiles.subs);
                    this.updateUploadArea(this.uploadAreas[2], 'subs', data.subs.name, true);
                    
                    // 更新字幕文件选择框选项
                    this.updateSubtitleFileSelect(data.subs.name);
                    
                    // 重新获取字幕文件名元素并绑定悬浮事件
                    const subsUploadArea = this.uploadAreas[2];
                    if (subsUploadArea) {
                        const subsFilenameHover = subsUploadArea.querySelector('.subs-upload-filename-hover');
                        if (subsFilenameHover) {
                            // 移除旧的事件监听器（通过克隆节点）
                            const newSubsFilenameHover = subsFilenameHover.cloneNode(true);
                            subsFilenameHover.parentNode.replaceChild(newSubsFilenameHover, subsFilenameHover);
                            
                            // 获取相关元素
                            const subsHoverPreview = subsUploadArea.querySelector('.subs-upload-hover-preview');
                            const subsPreviewContent = subsUploadArea.querySelector('.subs-upload-preview-content');

                            if (subsHoverPreview && subsPreviewContent) {
                                let subsHoverShowTimeout = null;
                                let subsHoverTimeout = null;
                                
                                newSubsFilenameHover.addEventListener('mouseenter', () => {
                                    // 延迟0.5秒后显示悬浮预览
                                    subsHoverShowTimeout = setTimeout(() => {
                                        if (this.uploadedFiles.subs) {
                                            // 计算预览窗口位置
                                            const rect = newSubsFilenameHover.getBoundingClientRect();
                                            const previewWidth = 400;  // 预览窗口宽度
                                            
                                            // 计算水平位置，确保不超出屏幕右边界
                                            let leftPos = rect.left + window.scrollX;
                                            if (leftPos + previewWidth > window.innerWidth) {
                                                leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
                                            }
                                            
                                            // 计算垂直位置，优先显示在下方，如果空间不够则显示在上方
                                            let topPos;
                                            const spaceBelow = window.innerHeight - rect.bottom;
                                            const spaceAbove = rect.top;
                                            
                                            if (spaceBelow > 200) {  // 字幕预览高度较小
                                                // 下方空间足够，显示在下方
                                                topPos = rect.bottom + window.scrollY;
                                            } else if (spaceAbove > 200) {
                                                // 上方空间足够，显示在上方
                                                topPos = rect.top + window.scrollY - 200;
                                            } else {
                                                // 两处空间都不够，选择空间较大的一方
                                                if (spaceBelow >= spaceAbove) {
                                                    topPos = rect.bottom + window.scrollY;
                                                } else {
                                                    topPos = rect.top + window.scrollY - 200;
                                                }
                                            }
                                            
                                            // 应用计算的位置
                                            subsHoverPreview.style.top = topPos + 'px';
                                            subsHoverPreview.style.left = leftPos + 'px';
                                            
                                            // 显示悬浮预览
                                            subsHoverPreview.style.display = 'block';
                                            
                                            // 加载字幕内容
                                            const subtitleFilename = this.uploadedFiles.subs.filename || this.uploadedFiles.subs.name;
                                            console.log('恢复字幕文件，加载字幕内容:', subtitleFilename);
                                            this.loadSubtitleContentForPreview(subtitleFilename, subsPreviewContent);
                                        }
                                    }, 500);
                                });
                                
                                newSubsFilenameHover.addEventListener('mouseleave', () => {
                                    // 清除显示定时器
                                    clearTimeout(subsHoverShowTimeout);
                                    
                                    // 延迟隐藏，以便用户可以将鼠标移动到预览上
                                    setTimeout(() => {
                                        // 只有鼠标不在预览上时才隐藏
                                        if (!subsHoverPreview.matches(':hover')) {
                                            subsHoverTimeout = setTimeout(() => {
                                                // 隐藏悬浮预览
                                                subsHoverPreview.style.display = 'none';
                                            }, 100);
                                        }
                                    }, 300);
                                });
                                
                                subsHoverPreview.addEventListener('mouseenter', () => {
                                    // 当鼠标进入预览时，取消隐藏定时器
                                    clearTimeout(subsHoverTimeout);
                                });
                                
                                subsHoverPreview.addEventListener('mouseleave', () => {
                                    // 隐藏悬浮预览
                                    subsHoverTimeout = setTimeout(() => {
                                        subsHoverPreview.style.display = 'none';
                                    }, 200);
                                });
                            }
                        }
                    }
                }
                
                if (data.config) {
                    this.uploadedFiles.config = data.config;
                    console.log('恢复配置文件信息:', this.uploadedFiles.config);
                    this.updateUploadArea(this.configUploadArea, 'config', data.config.name, true);
                    // 注意：这里不再调用loadConfigFileIfExists，让checkAndLoadConfigFile方法统一处理
                }
                
                if (data.video) {
                    this.uploadedFiles.video = data.video;
                    console.log('恢复视频文件信息:', this.uploadedFiles.video);
                    this.updateUploadArea(this.videoUploadArea, 'video', data.video.name, true);
                }
                
                // 如果所有必需文件都已上传，显示下一区域并加载PDF信息
                if (this.uploadedFiles.pdf && this.uploadedFiles.audio && this.uploadedFiles.subs) {
                    console.log('所有必需文件已恢复，显示下一区域并加载PDF信息');
                    this.showNextSection();
                    this.loadPDFInfo();
                }
            } else {
                console.log('获取服务器文件列表失败:', data.error);
            }
        } catch (error) {
            console.error('检查服务器文件失败:', error);
        }
    }

    async checkAndLoadConfigFile() {
        // 防止重复调用
        if (this.isCheckingFiles) {
            console.log('正在检查文件中，跳过重复调用');
            return;
        }
        
        // 防止配置文件重复加载
        if (this.configLoaded) {
            console.log('配置文件已加载，跳过重复加载');
            return;
        }
        
        this.isCheckingFiles = true;
        
        try {
            // 获取书名
            const bookName = this.getCurrentBookName();
            if (!bookName) {
                console.log('无法获取书名，跳过配置文件检查');
                return;
            }
            
            // 首先调用checkExistingFiles方法，恢复已上传的文件
            console.log('页面刷新，检查并恢复已上传的文件');
            await this.checkExistingFiles();
            
            // 并行执行配置文件加载和视频检查，提高速度
            const tasks = [];
            
            // 只有在有上传文件的情况下才加载配置文件
            if (this.hasUploadedFiles()) {
                console.log('检测到已上传文件，尝试加载配置文件');
                tasks.push(
                    this.loadConfigFileIfExists(bookName).then(loaded => {
                        if (loaded) {
                            this.configLoaded = true;
                        }
                    })
                );
            } else {
                console.log('没有上传文件，跳过配置文件加载');
            }
            
            // 检查是否已存在对应的视频文件
            tasks.push(this.checkExistingVideo());
            
            // 并行执行所有任务
            await Promise.all(tasks);
        } catch (error) {
            console.error('检查配置文件失败:', error);
            // 即使检查失败，也不显示错误，只是不显示配置文件
        } finally {
            this.isCheckingFiles = false;
        }
    }
    
    // 获取当前书名
    getCurrentBookName() {
        try {
            // 1. 优先从URL参数中获取书名
            const urlParams = new URLSearchParams(window.location.search);
            const urlBookName = urlParams.get('book_name');
            if (urlBookName) {
                console.log('从URL参数获取书名:', urlBookName);
                return urlBookName;
            }
            
            // 2. 从上传的文件路径中提取书名
            if (this.uploadedFiles.pdf && this.uploadedFiles.pdf.path) {
                const pathParts = this.uploadedFiles.pdf.path.split('/');
                // 路径格式可能是: 电子书/书名/文件名
                const ebookIndex = pathParts.indexOf('电子书');
                if (ebookIndex !== -1 && ebookIndex + 1 < pathParts.length) {
                    const bookName = pathParts[ebookIndex + 1];
                    console.log('从PDF文件路径获取书名:', bookName);
                    return bookName;
                }
            }
            
            // 3. 从上传的文件名中提取书名
            if (this.uploadedFiles.pdf && this.uploadedFiles.pdf.name) {
                // 假设文件名格式为: 书名.pdf
                const nameWithoutExt = this.uploadedFiles.pdf.name.replace(/\.[^/.]+$/, '');
                console.log('从PDF文件名获取书名:', nameWithoutExt);
                return nameWithoutExt;
            }
            
            // 4. 从音频文件名中提取书名
            if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                const nameWithoutExt = this.uploadedFiles.audio.name.replace(/\.[^/.]+$/, '');
                console.log('从音频文件名获取书名:', nameWithoutExt);
                return nameWithoutExt;
            }
            
            // 5. 从字幕文件名中提取书名
            if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
                const nameWithoutExt = this.uploadedFiles.subs.name.replace(/\.[^/.]+$/, '');
                console.log('从字幕文件名获取书名:', nameWithoutExt);
                return nameWithoutExt;
            }
            
            // 6. 没有上传文件时，抛出错误而不是返回空字符串
            console.error('没有上传文件，无法确定书名');
            throw new Error('无法确定书名，请先上传文件');
        } catch (error) {
            console.error('获取书名失败:', error);
            throw new Error('获取书名失败: ' + error.message);
        }
    }
    
    // 自动检测配置文件和视频文件
    async autoDetectConfigAndVideo() {
        try {
            // 获取书名
            const bookName = this.getCurrentBookName();
            if (!bookName) return;
            
            // 获取可能的配置文件名和视频文件名
            let configFilename = '';
            let videoFilename = '';
            
            if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
                // 优先使用字幕文件名（去除扩展名）
                const baseName = this.uploadedFiles.subs.name.replace(/\.[^/.]+$/, '');
                configFilename = `${baseName}.json`;
                videoFilename = `${baseName}.mp4`;
            } else if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                // 其次使用音频文件名（去除扩展名）
                const baseName = this.uploadedFiles.audio.name.replace(/\.[^/.]+$/, '');
                configFilename = `${baseName}.json`;
                videoFilename = `${baseName}.mp4`;
            }
            
            // 检测配置文件
            if (!this.uploadedFiles.config && configFilename) {
                await this.tryLoadConfigFile(bookName, configFilename);
            }
            
            // 检测视频文件
            if (!this.uploadedFiles.video && videoFilename) {
                await this.tryLoadVideoFile(bookName, videoFilename);
            }
        } catch (error) {
            console.error('自动检测配置文件和视频文件失败:', error);
        }
    }
    
    // 尝试加载配置文件
    async tryLoadConfigFile(bookName, configFilename) {
        try {
            console.log('尝试加载配置文件:', configFilename);
            
            // 使用统一的配置文件加载方法
            await this.loadConfigFileIfExists(bookName);
        } catch (error) {
            console.error('尝试加载配置文件失败:', error);
        }
    }
    
    // 尝试加载视频文件
    async tryLoadVideoFile(bookName, videoFilename) {
        try {
            console.log('尝试加载视频文件:', videoFilename);
            
            // 检查视频文件是否存在
            const response = await fetch(`/api/check-file-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(videoFilename)}/video`);
            const data = await response.json();
            
            if (response.ok && data.exists) {
                // 视频文件存在，添加到已上传文件列表
                this.uploadedFiles.video = {
                    name: videoFilename,
                    filename: videoFilename,
                    path: data.path,
                    url: `/download/${bookName}/${videoFilename}`,
                    size: data.filesize,
                    metadata: data.metadata
                };
                
                // 更新视频文件显示 - REMOVED
                // const videoItem = document.getElementById('video-file-item');
                // const videoNameElement = document.getElementById('video-file-name');
                const videoInfoElement = document.getElementById('video-file-info');
                
                // videoItem.style.display = 'flex';
                // videoNameElement.textContent = videoFilename;
                
                // 构建视频文件信息字符串
                let infoText = `文件大小：${data.filesize || '未知大小'} | 创建时间：${data.create_time || '未知时间'}`;
                
                // 添加视频元数据信息
                if (data.metadata) {
                    const metadata = data.metadata;
                    if (metadata.resolution) {
                        infoText += ` | 分辨率：${metadata.resolution}`;
                    }
                    if (metadata.duration) {
                        infoText += ` | 时长：${metadata.duration}`;
                    }
                    if (metadata.codec) {
                        infoText += ` | 编码：${metadata.codec}`;
                    }
                    if (metadata.bitrate) {
                        infoText += ` | 比特率：${metadata.bitrate}`;
                    }
                    if (metadata.fps) {
                        infoText += ` | 帧率：${metadata.fps}`;
                    }
                }
                
                videoInfoElement.textContent = infoText;
                
                // 更新视频上传区域显示
                if (this.videoUploadArea) {
                    const videoInfoDiv = this.videoUploadArea.querySelector('.upload-info');
                    videoInfoDiv.innerHTML = `
                        <div class="text-success small">
                            ${videoFilename}
                        </div>
                    `;
                    this.videoUploadArea.classList.add('uploaded');
                }
                
                // 显示提示信息
                this.addLogEntry(`自动检测到视频文件: ${videoFilename}`);
                
                // 显示已存在的视频文件
                this.showExistingVideo(bookName, videoFilename, data);
            }
        } catch (error) {
            console.error('尝试加载视频文件失败:', error);
        }
    }

    // 尝试查找并上传同名字幕文件
    async tryUploadMatchingSubtitle(audioFilename, bookName) {
        try {
            console.log('=== 开始查找同名字幕文件 ===');
            console.log('音频文件名:', audioFilename);
            console.log('书名:', bookName);
            
            // 如果字幕文件已上传，则不再尝试
            if (this.uploadedFiles.subs) {
                console.log('字幕文件已上传，跳过自动查找');
                console.log('当前字幕文件信息:', this.uploadedFiles.subs);
                return;
            }
            
            // 从音频文件名中提取基础名称（不带扩展名）
            const baseName = audioFilename.replace(/\.[^/.]+$/, '');
            console.log('提取的基础名称:', baseName);
            
            // 尝试查找同名的.srt文件
            const possibleSubtitleNames = [
                `${baseName}.srt`,
                `${baseName}.SRT`,
                `${baseName}.txt`,
                `${baseName}.TXT`
            ];
            
            console.log('尝试查找同名字幕文件:', possibleSubtitleNames);
            console.log('使用书名:', bookName);
            
            // 调用后端API查找同名字幕文件
            console.log('发送请求到 /api/find-matching-subtitle');
            const response = await fetch('/api/find-matching-subtitle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    book_name: bookName,
                    audio_filename: audioFilename,
                    possible_names: possibleSubtitleNames
                })
            });
            
            console.log('API响应状态:', response.status);
            const data = await response.json();
            console.log('查找同名字幕文件响应:', data);
            
            if (response.ok && data.found) {
                console.log('=== 找到同名字幕文件 ===');
                console.log('字幕文件名:', data.subtitle_name);
                console.log('字幕文件路径:', data.subtitle_path);
                console.log('字幕文件大小:', data.file_size);
                
                // 创建模拟文件对象用于上传
                const subtitleFile = {
                    name: data.subtitle_name,
                    path: data.subtitle_path,
                    size: data.file_size,
                    type: 'subs'
                };
                
                // 模拟字幕文件上传成功
                this.uploadedFiles.subs = {
                    name: data.subtitle_name,
                    filename: data.subtitle_name,
                    path: data.subtitle_path,
                    size: data.file_size,
                    url: `/api/input-file/${encodeURIComponent(bookName)}/${encodeURIComponent(data.subtitle_name)}`,
                    book_name: bookName,
                    key: `${bookName}_${data.subtitle_name}`, // 修复：使用完整的file_key作为key
                    file_key: `${bookName}_${data.subtitle_name}` // 添加file_key属性，设置为完整键
                };
                
                // 将字幕文件加载到内存中
                try {
                    const loadResponse = await fetch('/api/load-subtitle-to-memory', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            book_name: bookName,
                            subtitle_filename: data.subtitle_name
                        })
                    });
                    
                    if (loadResponse.ok) {
                        const loadData = await loadResponse.json();
                        console.log('字幕文件已加载到内存:', loadData);

                        // 异步执行字幕格式验证，不阻塞界面
                        this.validateSubtitleFormat(bookName, data.subtitle_name).catch(error => {
                            console.error('字幕格式验证失败:', error);
                        });
                    } else {
                        console.error('加载字幕文件到内存失败:', await loadResponse.text());
                    }
                } catch (loadError) {
                    console.error('加载字幕文件到内存时发生错误:', loadError);
                }
                
                console.log('模拟字幕文件上传成功，更新uploadedFiles:', this.uploadedFiles);
                
                // 更新字幕上传区域显示
                const subsUploadArea = document.querySelector('.upload-area[data-type="subs"]');
                console.log('更新字幕上传区域显示');
                this.updateUploadArea(subsUploadArea, 'subs', data.subtitle_name, true);
                
                // 更新已上传文件列表
                console.log('更新已上传文件列表');
                this.updateUploadedFilesList('subs', data.subtitle_name);
                
                // 更新字幕文件选择框
                console.log('更新字幕文件选择框');
                this.updateSubtitleFileSelect(data.subtitle_name);
                
                // 设置默认输出文件名（仅在输出文件名为空时）
                this.setDefaultOutputNameIfNeeded();
                
                // 显示提示信息
                console.log('显示提示信息');
                this.addLogEntry(`自动找到同名字幕文件: ${data.subtitle_name}`);
                
                // 如果所有文件都已上传，进入下一步
                if (Object.keys(this.uploadedFiles).length === 3) {
                    console.log('所有文件已上传，进入下一步');
                    this.showNextSection();
                    this.loadPDFInfo();
                }
            } else {
                console.log('=== 未找到同名字幕文件 ===');
                console.log('未找到同名字幕文件，原因:', data.message || '未知原因');
            }
        } catch (error) {
            console.error('=== 查找同名字幕文件失败 ===');
            console.error('错误详情:', error);
            // 不显示错误，因为这不是关键功能
        }
    }

    // 获取当前书名
    getCurrentBookName() {
        console.log('=== 开始获取当前书名 ===');
        
        // 优先从当前作业获取
        if (this.currentJob && this.currentJob.book_name) {
            console.log('从当前作业获取书名:', this.currentJob.book_name);
            return this.currentJob.book_name;
        }
        
        // 从上传的文件中获取书名（后端已提供）
        if (this.uploadedFiles.pdf && this.uploadedFiles.pdf.book_name) {
            console.log('从PDF文件获取书名:', this.uploadedFiles.pdf.book_name);
            return this.uploadedFiles.pdf.book_name;
        }
        if (this.uploadedFiles.audio && this.uploadedFiles.audio.book_name) {
            console.log('从音频文件获取书名:', this.uploadedFiles.audio.book_name);
            return this.uploadedFiles.audio.book_name;
        }
        if (this.uploadedFiles.subs && this.uploadedFiles.subs.book_name) {
            console.log('从字幕文件获取书名:', this.uploadedFiles.subs.book_name);
            return this.uploadedFiles.subs.book_name;
        }
        
        // 从上传的文件路径中提取书名
        if (this.uploadedFiles.pdf && this.uploadedFiles.pdf.path) {
            const pathParts = this.uploadedFiles.pdf.path.split('/');
            console.log('PDF文件路径部分:', pathParts);
            if (pathParts.includes('电子书') && pathParts.length > pathParts.indexOf('电子书') + 1) {
                const bookName = pathParts[pathParts.indexOf('电子书') + 1];
                console.log('从PDF文件路径提取书名:', bookName);
                return bookName;
            }
        }
        
        if (this.uploadedFiles.audio && this.uploadedFiles.audio.path) {
            const pathParts = this.uploadedFiles.audio.path.split('/');
            console.log('音频文件路径部分:', pathParts);
            if (pathParts.includes('电子书') && pathParts.length > pathParts.indexOf('电子书') + 1) {
                const bookName = pathParts[pathParts.indexOf('电子书') + 1];
                console.log('从音频文件路径提取书名:', bookName);
                return bookName;
            }
        }
        
        if (this.uploadedFiles.subs && this.uploadedFiles.subs.path) {
            const pathParts = this.uploadedFiles.subs.path.split('/');
            console.log('字幕文件路径部分:', pathParts);
            if (pathParts.includes('电子书') && pathParts.length > pathParts.indexOf('电子书') + 1) {
                const bookName = pathParts[pathParts.indexOf('电子书') + 1];
                console.log('从字幕文件路径提取书名:', bookName);
                return bookName;
            }
        }
        
        // 从文件名中提取书名（去掉扩展名）
        if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
            const bookName = this.uploadedFiles.audio.name.replace(/\.[^/.]+$/, '');
            console.log('从音频文件名提取书名:', bookName);
            return bookName;
        }
        
        if (this.uploadedFiles.pdf && this.uploadedFiles.pdf.name) {
            const bookName = this.uploadedFiles.pdf.name.replace(/\.[^/.]+$/, '');
            console.log('从PDF文件名提取书名:', bookName);
            return bookName;
        }
        
        if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
            const bookName = this.uploadedFiles.subs.name.replace(/\.[^/.]+$/, '');
            console.log('从字幕文件名提取书名:', bookName);
            return bookName;
        }
        
        // 如果都获取不到，返回默认值
        console.log('无法获取书名，返回默认值: unknown');
        return 'unknown';
    }

    // 检查已存在的视频文件
    async checkExistingVideo() {
        try {
            // 获取书名
            const bookName = this.getCurrentBookName();
            console.log('检查已存在视频文件，书名:', bookName);
            if (!bookName) return;
            
            // 获取可能的视频文件名（优先使用字幕文件名作为基准，与后端逻辑保持一致）
            let videoFilename = '';
            if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
                // 优先使用字幕文件名（去除扩展名）
                videoFilename = this.uploadedFiles.subs.name.replace(/\.[^/.]+$/, '') + '.mp4';
            } else if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                // 其次使用音频文件名（去除扩展名）
                videoFilename = this.uploadedFiles.audio.name.replace(/\.[^/.]+$/, '') + '.mp4';
            }
            
            console.log('检查视频文件是否存在:', videoFilename);
            if (!videoFilename) return;
            
            // 添加超时控制
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 5000); // 5秒超时
            
            // 检查视频文件是否存在
            const response = await fetch(`/api/check-file-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(videoFilename)}/video`, {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            const data = await response.json();
            
            console.log('视频文件检查结果:', data);
            
            if (response.ok && data.exists) {
                // 视频文件存在，显示在结果区域
                this.showExistingVideo(bookName, videoFilename, data);
            }
        } catch (error) {
            console.error('检查已存在视频文件失败:', error);
        }
    }

    // 显示已存在的视频文件
    async showExistingVideo(bookName, videoFilename, videoData) {
        console.log('显示已存在的视频文件:', bookName, videoFilename, videoData);
        
        // 显示结果区域
        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'block';
        
        // 设置视频文件信息
        this.resultFilename.textContent = videoFilename;
        this.resultTime.textContent = videoData.create_time || new Date().toLocaleString();
        
        // 使用updateMainResultVideoInfo方法更新完整的视频信息
        this.updateMainResultVideoInfo(videoFilename, videoData);
        
        // 设置下载链接
        this.downloadLink.href = `/download/${bookName}/${videoFilename}`;
        
        // 显示"打开本地目录"按钮
        const openDirectoryBtn = document.getElementById('open-directory-btn');
        if (openDirectoryBtn) {
            openDirectoryBtn.style.display = 'inline-block';
            openDirectoryBtn.setAttribute('data-book-name', bookName);
        }
        
        // 设置提示信息为"视频已存在"
        const resultsMessage = document.getElementById('results-message');
        const resultsAlert = document.getElementById('results-alert');
        if (resultsMessage && resultsAlert) {
            resultsMessage.textContent = '视频已存在';
            // 将alert样式从success改为info，以区分新创建的视频和已存在的视频
            resultsAlert.className = 'alert alert-info';
            const icon = resultsAlert.querySelector('i');
            if (icon) {
                icon.className = 'bi bi-info-circle-fill me-2';
            }
        }
        
        // 在已上传文件列表中显示视频文件信息
        this.displayVideoFileInUploadedList(videoFilename, videoData);
        console.log('视频文件显示完成');
    }
    
    // 在已上传文件列表中显示视频文件信息 - REMOVED
    displayVideoFileInUploadedList(videoFilename, videoData) {
        console.log('在已上传文件列表中显示视频文件:', videoFilename, videoData);
        return; // File info list has been removed
        
        // 获取视频文件项元素
        const videoFileItem = document.getElementById('video-file-item');
        const videoFileName = document.getElementById('video-file-name');
        const videoFileInfo = document.getElementById('video-file-info');
        
        if (videoFileItem && videoFileName && videoFileInfo) {
            console.log('找到视频文件相关元素，开始设置');
            
            // 设置视频文件名
            videoFileName.textContent = videoFilename;
            
            // 构建视频文件信息字符串
            let infoText = `文件大小：${videoData.filesize || '未知大小'} | 创建时间：${videoData.create_time || '未知时间'}`;
            
            // 添加视频元数据信息
            if (videoData.metadata) {
                const metadata = videoData.metadata;
                if (metadata.resolution) {
                    infoText += ` | 分辨率：${metadata.resolution}`;
                }
                if (metadata.duration) {
                    infoText += ` | 时长：${metadata.duration}`;
                }
                if (metadata.codec) {
                    infoText += ` | 编码：${metadata.codec}`;
                }
                if (metadata.bitrate) {
                    infoText += ` | 比特率：${metadata.bitrate}`;
                }
                if (metadata.fps) {
                    infoText += ` | 帧率：${metadata.fps}`;
                }
            }
            
            videoFileInfo.textContent = infoText;
            
            // 存储视频文件信息，以便在预览时使用
            this.videoFileInfo = {
                filename: videoFilename,
                data: videoData
            };
            
            // 显示视频文件项
            videoFileItem.style.display = 'flex';
            console.log('视频文件项已显示');
            
            // 更新视频上传区域显示
            if (this.videoUploadArea) {
                const videoInfoDiv = this.videoUploadArea.querySelector('.upload-info');
                videoInfoDiv.innerHTML = `
                    <div class="text-success small">
                        ${videoFilename}
                    </div>
                `;
                this.videoUploadArea.classList.add('uploaded');
            }
            
            // 添加视频文件到已上传文件列表
            this.uploadedFiles.video = {
                name: videoFilename,
                filename: videoFilename,
                path: videoData.path,
                url: `/download/${this.getCurrentBookName()}/${videoFilename}`,
                size: videoData.filesize,
                metadata: videoData.metadata
            };
        } else {
            console.error('未找到视频文件相关元素:', {
                videoFileItem: !!videoFileItem,
                videoFileName: !!videoFileName,
                videoFileInfo: !!videoFileInfo
            });
        }
    }

    showNextSection() {
        this.timingSection.style.display = 'block';
        this.deepseekSection.style.display = 'block';
        this.pageTimingSection.style.display = 'block';
        this.settingsSection.style.display = 'block';
        this.createSection.style.display = 'block';
    }

    async loadPDFInfo() {
        try {
            const response = await fetch('/api/get-pdf-pages', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    pdf_path: this.uploadedFiles.pdf.path
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.pageCount = data.page_count;
                this.pageTimings = data.suggested_timings;
                
                // Set max values for page inputs - check if elements exist first
                if (this.endPage) {
                    this.endPage.max = this.pageCount;
                }
                if (this.startPage) {
                    this.startPage.max = this.pageCount;
                }
                if (this.timingEndPage) {
                    this.timingEndPage.max = this.pageCount;
                }
                if (this.timingStartPage) {
                    this.timingStartPage.max = this.pageCount;
                }
                
                // Update page count display only if page range is set
                if (this.timingStartPage.value && this.timingEndPage.value) {
                    const startPage = parseInt(this.timingStartPage.value) || 1;
                    const endPage = parseInt(this.timingEndPage.value) || this.pageCount;
                    this.updatePageCountDisplay(endPage - startPage);
                } else {
                    this.updatePageCountDisplay(0);
                }
                
                // Generate initial timing inputs
                this.generatePageTimingInputs();
                
                // 不在程序启动时自动生成时间点，避免显示提示
                // if (this.audioDuration > 0) {
                //     this.generateTimings();
                // }
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            this.showError(`PDF信息加载失败: ${error.message}`);
        }
    }

    generatePageTimingInputs() {
        console.log('generatePageTimingInputs方法被调用');
        this.addLogEntry('开始生成翻页点输入框');
        console.log('当前页面范围:', this.timingStartPage.value, '到', this.timingEndPage.value);
        this.addLogEntry(`当前页面范围: ${this.timingStartPage.value} 到 ${this.timingEndPage.value}`);
        console.log('当前竖排布局设置:', this.verticalLayout.checked);
        this.addLogEntry(`当前竖排布局设置: ${this.verticalLayout.checked}`);
        console.log('当前翻页点数据:', this.pageTimings);
        this.addLogEntry(`当前翻页点数据: ${JSON.stringify(this.pageTimings)}`);
        
        this.pageTimingsGrid.innerHTML = '';

        // Check if page range is empty
        if (!this.timingStartPage.value || !this.timingEndPage.value) {
            console.log('页面范围为空，显示提示信息');
            console.log('timingStartPage.value:', this.timingStartPage.value);
            console.log('timingEndPage.value:', this.timingEndPage.value);
            this.addLogEntry('页面范围为空，跳过生成翻页点输入框');
            this.addLogEntry(`起始页值: ${this.timingStartPage.value}, 结束页值: ${this.timingEndPage.value}`);
            // 不在程序启动时显示提示，仅在用户尝试操作时才提示
            return;
        }

        const startPage = parseInt(this.timingStartPage.value);
        const endPage = parseInt(this.timingEndPage.value);
        const isVerticalLayout = this.verticalLayout.checked;
        
        console.log('解析后的页面范围:', startPage, '到', endPage);
        this.addLogEntry(`解析后的页面范围: ${startPage} 到 ${endPage}`);
        console.log('是否竖排布局:', isVerticalLayout);
        this.addLogEntry(`是否竖排布局: ${isVerticalLayout}`);

        // 确保pageTimings数组有足够的长度
        const maxIndex = isVerticalLayout ? 
            Math.floor((endPage - startPage) / 2) : 
            (endPage - startPage);
        
        if (this.pageTimings.length < maxIndex) {
            console.log(`扩展pageTimings数组从${this.pageTimings.length}到${maxIndex}`);
            this.addLogEntry(`扩展pageTimings数组从${this.pageTimings.length}到${maxIndex}`);
            for (let i = this.pageTimings.length; i < maxIndex; i++) {
                // 只有当原数组不为空时才填充0，否则保持undefined
                this.pageTimings[i] = this.pageTimings.length > 0 ? 0 : undefined;
            }
        }

        // 根据布局模式调整翻页点逻辑
        if (isVerticalLayout) {
            console.log('使用竖排布局模式');
            this.addLogEntry('使用竖排布局模式');
            // 竖排模式：两页合并为一个背景，翻页点数量减半
            // 确保页数是偶数，如果不是则减1
            const adjustedEndPage = endPage % 2 === 0 ? endPage : endPage - 1;
            console.log('调整后的结束页:', adjustedEndPage);
            this.addLogEntry(`调整后的结束页: ${adjustedEndPage}`);
            
            // 为每对页面创建输入框（从startPage到adjustedEndPage，每次增加2页）
            let timingIndex = 0; // 翻页点数组的索引
            for (let i = startPage - 1; i < adjustedEndPage - 1; i += 2) {
                console.log('创建翻页点输入框:', i, '页到', i+2, '页');
                this.addLogEntry(`创建翻页点输入框: 第${i+1}-${i+2}页到第${i+3}-${i+4}页`);
                console.log('使用翻页点数组索引:', timingIndex, '值:', this.pageTimings[timingIndex]);
                this.addLogEntry(`使用翻页点数组索引: ${timingIndex}, 值: ${this.pageTimings[timingIndex]}`);
                const col = document.createElement('div');
                col.className = 'col-md-2 col-sm-4 col-6';

                col.innerHTML = `
                    <div class="page-timing-input">
                        <label class="form-label small">第 ${i + 1}-${i + 2} 页 → 第 ${i + 3}-${i + 4} 页</label>
                        <div class="input-group input-group-sm">
                            <input type="text"
                                   class="form-control page-timing"
                                   data-page="${i}"
                                   value="${this.pageTimings[timingIndex] !== undefined ? this.pageTimings[timingIndex] : ''}"
                                   placeholder="00:00:38,540 或 38.54"
                                   style="width: 50%;">
                            <span class="input-group-text">秒</span>
                        </div>
                    </div>
                `;

                this.pageTimingsGrid.appendChild(col);
                timingIndex++; // 增加翻页点数组索引
            }

            // 如果只有一对页面或没有完整的页面对，显示提示信息
            if (adjustedEndPage - startPage < 2) {
                const col = document.createElement('div');
                col.className = 'col-12';
                col.innerHTML = `
                    <div class="alert alert-info">
                        <i class="bi bi-info-circle me-2"></i>
                        竖排模式下至少需要两页（一对页面）才能设置翻页时间点。
                    </div>
                `;
                this.pageTimingsGrid.appendChild(col);
            }
            
            // 更新翻页点数量显示
            const numTransitions = Math.floor((adjustedEndPage - startPage) / 2);
            console.log('翻页点数量:', numTransitions);
            this.addLogEntry(`竖排模式翻页点数量: ${numTransitions}`);
            this.updatePageCountDisplay(numTransitions);
        } else {
            console.log('使用普通布局模式');
            this.addLogEntry('使用普通布局模式');
            // 普通模式：为每个翻页点创建输入框（从startPage到endPage-1）
            let timingIndex = 0; // 翻页点数组的索引
            for (let i = startPage - 1; i < endPage - 1; i++) {
                console.log('创建翻页点输入框:', i, '页到', i+1, '页');
                this.addLogEntry(`创建翻页点输入框: 第${i+1}页到第${i+2}页`);
                console.log('使用翻页点数组索引:', timingIndex, '值:', this.pageTimings[timingIndex]);
                this.addLogEntry(`使用翻页点数组索引: ${timingIndex}, 值: ${this.pageTimings[timingIndex]}`);
                const col = document.createElement('div');
                col.className = 'col-md-2 col-sm-4 col-6';

                col.innerHTML = `
                    <div class="page-timing-input">
                        <label class="form-label small">第 ${i + 1} 页 → 第 ${i + 2} 页</label>
                        <div class="input-group input-group-sm">
                            <input type="text"
                                   class="form-control page-timing"
                                   data-page="${i}"
                                   value="${this.pageTimings[timingIndex] !== undefined ? this.pageTimings[timingIndex] : ''}"
                                   placeholder="00:00:38,540 或 38.54"
                                   style="width: 50%;">
                            <span class="input-group-text">秒</span>
                        </div>
                    </div>
                `;

                this.pageTimingsGrid.appendChild(col);
                timingIndex++; // 增加翻页点数组索引
            }

            // 如果只有一页，显示提示信息
            if (startPage === endPage) {
                const col = document.createElement('div');
                col.className = 'col-12';
                col.innerHTML = `
                    <div class="alert alert-info">
                        <i class="bi bi-info-circle me-2"></i>
                        只选择了一页，无需设置翻页时间点。
                    </div>
                `;
                this.pageTimingsGrid.appendChild(col);
            }
            
            // 更新翻页点数量显示
            const numTransitions = endPage - startPage;
            console.log('翻页点数量:', numTransitions);
            this.addLogEntry(`普通模式翻页点数量: ${numTransitions}`);
            this.updatePageCountDisplay(numTransitions);
        }

        // Bind change events
        document.querySelectorAll('.page-timing').forEach(input => {
            input.addEventListener('input', () => {
                // Check if the input is in SRT time format (HH:MM:SS,mmm)
                const value = input.value.trim();
                const srtTimeMatch = value.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})/);
                
                if (srtTimeMatch) {
                    // Convert SRT time format to seconds
                    const timeInSeconds = this.parseTimeToSeconds(
                        srtTimeMatch[1], 
                        srtTimeMatch[2], 
                        srtTimeMatch[3], 
                        srtTimeMatch[4]
                    );
                    
                    // Update the input value with the converted time in seconds
                    input.value = timeInSeconds.toFixed(3);
                }
                
                this.updateTotalDuration();
            });
            
            // Add blur event to handle when user leaves the input field
            input.addEventListener('blur', () => {
                // Check if the input is in SRT time format (HH:MM:SS,mmm)
                const value = input.value.trim();
                const srtTimeMatch = value.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})/);
                
                if (srtTimeMatch) {
                    // Convert SRT time format to seconds
                    const timeInSeconds = this.parseTimeToSeconds(
                        srtTimeMatch[1], 
                        srtTimeMatch[2], 
                        srtTimeMatch[3], 
                        srtTimeMatch[4]
                    );
                    
                    // Update the input value with the converted time in seconds
                    input.value = timeInSeconds.toFixed(3);
                    this.updateTotalDuration();
                }
            });
        });
        
        console.log('generatePageTimingInputs方法执行完成');
        this.addLogEntry('翻页点输入框生成完成');
    }

    async generateTimingsFromSubtitles() {
        // Check if page range is empty
        if (!this.timingStartPage.value || !this.timingEndPage.value) {
            this.showError('请先设置PDF页面范围');
            return;
        }

        // Check if subtitle file is uploaded
        if (!this.uploadedFiles.subs) {
            this.showError('请先上传字幕文件');
            return;
        }

        // Validate inputs
        const startPage = parseInt(this.timingStartPage.value);
        const endPage = parseInt(this.timingEndPage.value);

        if (isNaN(startPage) || isNaN(endPage) || startPage < 1 || endPage > this.pageCount || startPage > endPage) {
            this.showError('请输入有效的页码范围');
            return;
        }

        try {
            // 显示加载状态
            this.showLoading('正在从字幕文件提取翻页时间点...');
            
            // 准备API请求数据
            const requestData = {
                book_name: this.currentBookName || '红楼梦',
                subtitle_filename: this.uploadedFiles.subs.name,
                start_page: startPage,
                end_page: endPage,
                is_vertical_layout: this.verticalLayout.checked
            };
            
            // 如果有页面内容，添加到请求中
            if (this.pageContent && this.pageContent.length >= endPage) {
                requestData.page_content = this.pageContent.slice(0, endPage);
            }
            
            // 调用后端API
            const response = await fetch('/api/extract-timings-from-subtitles', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            
            // 计算翻页点数量
            let numTransitions;
            const isVerticalLayout = this.verticalLayout.checked;
            
            if (isVerticalLayout) {
                // 竖排模式：两页合并为一个背景，翻页点数量减半
                const adjustedEndPage = endPage % 2 === 0 ? endPage : endPage - 1;
                numTransitions = Math.floor((adjustedEndPage - startPage) / 2);
            } else {
                // 普通模式
                numTransitions = endPage - startPage;
            }
            
            // 确保pageTimings数组有足够的长度
            if (this.pageTimings.length < this.pageCount) {
                for (let i = this.pageTimings.length; i < this.pageCount; i++) {
                    this.pageTimings[i] = 0;
                }
            }
            
            // 应用API返回的时间点
            if (result.page_timings && result.page_timings.length > 0) {
                // 清空范围内的现有时间点
                for (let i = startPage - 1; i < endPage; i++) {
                    this.pageTimings[i] = 0;
                }
                
                // 设置新的时间点
                for (let i = 0; i < result.page_timings.length; i++) {
                    let pageIndex;
                    
                    if (isVerticalLayout) {
                        // 竖排模式：每个时间点对应两页
                        pageIndex = startPage - 1 + (i * 2);
                        
                        // 为两页设置相同的时间点
                        if (pageIndex < this.pageCount) {
                            this.pageTimings[pageIndex] = result.page_timings[i];
                        }
                        if (pageIndex + 1 < this.pageCount) {
                            this.pageTimings[pageIndex + 1] = result.page_timings[i];
                        }
                    } else {
                        // 普通模式：每个时间点对应一页
                        pageIndex = startPage - 1 + i;
                        
                        if (pageIndex < this.pageCount) {
                            this.pageTimings[pageIndex] = result.page_timings[i];
                        }
                    }
                }
                
                console.log('已应用从字幕提取的翻页时间点:', result.page_timings);
            } else {
                // 如果API返回空的时间点，使用默认方法
                console.warn('API返回空的时间点，使用默认方法');
                this.generateTimings();
                return;
            }
            
            // 更新UI
            this.generatePageTimingInputs();
            this.updateTotalDuration();
            this.updatePageCountDisplay(numTransitions);
            
            // 显示成功消息
            this.showSuccess(`已根据字幕文件自动提取${result.page_timings.length}个翻页时间点`);
            
        } catch (error) {
            console.error('从字幕提取翻页时间点失败:', error);
            this.showError('从字幕提取翻页时间点失败: ' + error.message);
            // 回退到默认方法
            this.generateTimings();
        } finally {
            this.hideLoading();
        }
    }

    parseSubtitleTimings(subtitleText) {
        // Split subtitle text by double newlines (standard SRT format)
        const subtitleBlocks = subtitleText.trim().split(/\r?\n\r?\n/);
        const timings = [];
        
        subtitleBlocks.forEach(block => {
            const lines = block.split(/\r?\n/);
            
            if (lines.length >= 3) {
                const timeRange = lines[1];
                const text = lines.slice(2).join('\n');
                
                // Parse time range (format: 00:00:00,000 --> 00:00:00,000)
                const timeMatch = timeRange.match(/(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})/);
                
                if (timeMatch) {
                    const startTime = this.parseTimeToSeconds(timeMatch[1], timeMatch[2], timeMatch[3], timeMatch[4]);
                    const endTime = this.parseTimeToSeconds(timeMatch[5], timeMatch[6], timeMatch[7], timeMatch[8]);
                    
                    timings.push({
                        startTime,
                        endTime,
                        text
                    });
                }
            }
        });
        
        return timings;
    }

    parseTimeToSeconds(hours, minutes, seconds, milliseconds) {
        return parseInt(hours) * 3600 + parseInt(minutes) * 60 + parseInt(seconds) + parseInt(milliseconds) / 1000;
    }

    updatePageCountDisplay(count) {
        // 更新翻页点数显示
        const pageCountElement = document.getElementById('page-count');
        if (pageCountElement) {
            pageCountElement.textContent = count;
        }
    }

    updatePageTimingInputs() {
        console.log('updatePageTimingInputs方法被调用');
        
        const startPage = parseInt(this.timingStartPage.value);
        const endPage = parseInt(this.timingEndPage.value);
        const isVerticalLayout = this.verticalLayout.checked;
        
        console.log('页面范围:', startPage, '到', endPage);
        console.log('是否竖排布局:', isVerticalLayout);
        
        let timingIndex = 0; // 翻页点数组的索引
        
        document.querySelectorAll('.page-timing').forEach(input => {
            const pageIndex = parseInt(input.dataset.page);
            console.log(`更新输入框 - 页码索引: ${pageIndex}, 翻页点数组索引: ${timingIndex}, 值: ${this.pageTimings[timingIndex]}`);
            input.value = this.pageTimings[timingIndex] || 0;
            timingIndex++; // 增加翻页点数组索引
        });
        
        console.log('updatePageTimingInputs方法执行完成');
    }

    updateTotalDuration() {
        console.log('updateTotalDuration方法被调用');
        this.addLogEntry('开始更新总时长');
        console.log('当前页面范围:', this.timingStartPage.value, '到', this.timingEndPage.value);
        this.addLogEntry(`当前页面范围: ${this.timingStartPage.value} 到 ${this.timingEndPage.value}`);
        console.log('当前竖排布局设置:', this.verticalLayout.checked);
        this.addLogEntry(`当前竖排布局设置: ${this.verticalLayout.checked}`);
        
        // Get current manual timings
        let timingIndex = 0; // 翻页点数组的索引
        document.querySelectorAll('.page-timing').forEach(input => {
            const pageIndex = parseInt(input.dataset.page);
            console.log(`更新pageTimings数组 - 页码索引: ${pageIndex}, 翻页点数组索引: ${timingIndex}, 值: ${input.value}`);
            this.addLogEntry(`更新pageTimings数组 - 页码索引: ${pageIndex}, 翻页点数组索引: ${timingIndex}, 值: ${input.value}`);
            this.pageTimings[timingIndex] = parseFloat(input.value) || 0;
            timingIndex++; // 增加翻页点数组索引
        });

        // Calculate total duration for page transitions in the selected range
        if (!this.timingStartPage.value || !this.timingEndPage.value) {
            console.log('页面范围为空，设置总时长为0');
            this.addLogEntry('页面范围为空，设置总时长为0');
            this.totalDuration.textContent = '0.0';
            return;
        }

        const startPage = parseInt(this.timingStartPage.value);
        const endPage = parseInt(this.timingEndPage.value);
        let total = 0;
        
        console.log('计算总时长，页面范围:', startPage, '到', endPage);
        this.addLogEntry(`计算总时长，页面范围: ${startPage} 到 ${endPage}`);
        
        // Check if vertical layout is enabled
        const isVerticalLayout = this.verticalLayout.checked;
        console.log('是否竖排布局:', isVerticalLayout);
        this.addLogEntry(`是否竖排布局: ${isVerticalLayout}`);
        
        if (isVerticalLayout) {
            // 竖排模式：两页合并为一个背景，只计算偶数页面的时间
            const adjustedEndPage = endPage % 2 === 0 ? endPage : endPage - 1;
            console.log('调整后的结束页:', adjustedEndPage);
            this.addLogEntry(`竖排模式调整后的结束页: ${adjustedEndPage}`);
            
            timingIndex = 0; // 重置翻页点数组的索引
            for (let i = startPage - 1; i < adjustedEndPage - 1; i += 2) {
                if (this.pageTimings[timingIndex] > 0) {
                    console.log(`添加翻页点 ${timingIndex} 的时间:`, this.pageTimings[timingIndex]);
                    this.addLogEntry(`添加翻页点 ${timingIndex} 的时间: ${this.pageTimings[timingIndex]}`);
                    total += this.pageTimings[timingIndex];
                }
                timingIndex++; // 增加翻页点数组索引
            }
        } else {
            // 普通模式：计算所有页面的时间
            timingIndex = 0; // 重置翻页点数组的索引
            for (let i = startPage - 1; i < endPage - 1; i++) {
                if (this.pageTimings[timingIndex] > 0) {
                    console.log(`添加翻页点 ${timingIndex} 的时间:`, this.pageTimings[timingIndex]);
                    this.addLogEntry(`添加翻页点 ${timingIndex} 的时间: ${this.pageTimings[timingIndex]}`);
                    total += this.pageTimings[timingIndex];
                }
                timingIndex++; // 增加翻页点数组索引
            }
        }

        console.log('计算出的总时长:', total);
        this.addLogEntry(`计算出的总时长: ${total}`);
        this.totalDuration.textContent = total.toFixed(1);

        // Update audio duration if available
        if (this.uploadedFiles.audio) {
            this.getAudioDuration();
        }
        
        console.log('updateTotalDuration方法执行完成');
        this.addLogEntry('总时长更新完成');
    }

    resetTimings() {
        // Check if page range is set
        if (!this.timingStartPage.value || !this.timingEndPage.value) {
            this.showError('请先设置PDF页面范围');
            return;
        }

        // Reset all page timings to 0
        const startPage = parseInt(this.timingStartPage.value);
        const endPage = parseInt(this.timingEndPage.value);

        for (let i = 0; i < this.pageCount; i++) {
            if (i >= startPage - 1 && i < endPage - 1) {
                this.pageTimings[i] = 0;
            }
        }

        // Update the UI
        this.generatePageTimingInputs();
        this.updateTotalDuration();
        
        this.showSuccess('已重置所有翻页时间点');
    }

    generateTimings() {
        // Check if page range is set
        if (!this.timingStartPage.value || !this.timingEndPage.value) {
            this.showError('请先设置PDF页面范围');
            return;
        }

        const startPage = parseInt(this.timingStartPage.value);
        const endPage = parseInt(this.timingEndPage.value);
        const isVerticalLayout = this.verticalLayout.checked;
        
        // Calculate number of transitions
        let numTransitions;
        if (isVerticalLayout) {
            // 竖排模式：两页合并为一个背景，翻页点数量减半
            const adjustedEndPage = endPage % 2 === 0 ? endPage : endPage - 1;
            numTransitions = Math.floor((adjustedEndPage - startPage) / 2);
        } else {
            // 普通模式：每个页面翻页点
            numTransitions = endPage - startPage;
        }
        
        if (numTransitions <= 0) {
            this.showError('页面范围无效，无法生成翻页时间点');
            return;
        }
        
        // 确保pageTimings数组有足够的长度
        if (this.pageTimings.length < numTransitions) {
            console.log(`扩展pageTimings数组从${this.pageTimings.length}到${numTransitions}`);
            for (let i = this.pageTimings.length; i < numTransitions; i++) {
                this.pageTimings[i] = 0;
            }
        }
        
        // Get audio duration if available, otherwise use default
        let totalAudioDuration = this.audioDuration || 0;
        
        // If no audio duration, try to get it from uploaded audio file
        if (totalAudioDuration === 0 && this.uploadedFiles.audio) {
            this.getAudioDurationFromFile(this.uploadedFiles.audio)
                .then(() => {
                    totalAudioDuration = this.audioDuration;
                    this.calculateAndApplyTimings(numTransitions, totalAudioDuration, isVerticalLayout);
                })
                .catch(error => {
                    console.error('Failed to get audio duration:', error);
                    // Use default duration if audio duration can't be retrieved
                    totalAudioDuration = numTransitions * 30; // 30 seconds per transition as default
                    this.calculateAndApplyTimings(numTransitions, totalAudioDuration, isVerticalLayout);
                });
        } else {
            // Use default duration if no audio available
            if (totalAudioDuration === 0) {
                totalAudioDuration = numTransitions * 30; // 30 seconds per transition as default
            }
            this.calculateAndApplyTimings(numTransitions, totalAudioDuration, isVerticalLayout);
        }
    }
    
    calculateAndApplyTimings(numTransitions, totalAudioDuration, isVerticalLayout) {
        // Calculate average duration per transition
        const avgDurationPerTransition = totalAudioDuration / numTransitions;
        
        // 确保pageTimings数组有足够的长度
        if (this.pageTimings.length < numTransitions) {
            console.log(`扩展pageTimings数组从${this.pageTimings.length}到${numTransitions}`);
            for (let i = this.pageTimings.length; i < numTransitions; i++) {
                this.pageTimings[i] = 0;
            }
        }
        
        // Apply timings to pageTimings array
        let timingIndex = 0;
        if (isVerticalLayout) {
            // 竖排模式：为每对页面设置时间
            const startPage = parseInt(this.timingStartPage.value);
            const endPage = parseInt(this.timingEndPage.value);
            const adjustedEndPage = endPage % 2 === 0 ? endPage : endPage - 1;
            
            for (let i = startPage - 1; i < adjustedEndPage - 1; i += 2) {
                this.pageTimings[timingIndex] = avgDurationPerTransition;
                timingIndex++;
            }
        } else {
            // 普通模式：为每个页面设置时间
            const startPage = parseInt(this.timingStartPage.value);
            const endPage = parseInt(this.timingEndPage.value);
            
            for (let i = startPage - 1; i < endPage - 1; i++) {
                this.pageTimings[timingIndex] = avgDurationPerTransition;
                timingIndex++;
            }
        }
        
        // Update the UI
        this.generatePageTimingInputs();
        this.updateTotalDuration();
        
        this.showSuccess(`已生成${numTransitions}个翻页时间点，平均每个${avgDurationPerTransition.toFixed(1)}秒`);
    }

    async getAudioDurationFromFile(file) {
        try {
            // Create an audio element to get duration
            const audio = new Audio();
            audio.src = URL.createObjectURL(file);
            
            // Wait for metadata to load
            await new Promise((resolve, reject) => {
                audio.addEventListener('loadedmetadata', resolve);
                audio.addEventListener('error', reject);
            });
            
            this.audioDuration = audio.duration;
            
            // Clean up
            URL.revokeObjectURL(audio.src);
        } catch (error) {
            console.error('Failed to get audio duration:', error);
            // Fallback to default duration
            this.audioDuration = 0;
        }
    }

    async getAudioDuration() {
        try {
            // Get duration from audio player if available
            if (this.audioPlayer && this.audioPlayer.duration) {
                this.audioDuration = this.audioPlayer.duration;
            }
        } catch (error) {
            console.error('Failed to get audio duration:', error);
        }
    }

    showSubtitleSection() {
        const subtitleSection = document.getElementById('subtitle-extraction-section');
        const extractBtn = document.getElementById('extract-subtitle-btn');
        
        if (subtitleSection) {
            subtitleSection.style.display = 'block';
            
            // 注释掉自动滚动功能，保持页面位置不变
            // setTimeout(() => {
            //     subtitleSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            // }, 300);
            
            // 启用提取按钮
            if (extractBtn && this.uploadedFiles.audio) {
                extractBtn.disabled = false;
            }
            
            // 加载模型信息并更新下拉框
            this.loadModelStatusAndUpdateSelect();
            
            // 记录日志
            this.addLogEntry('字幕提取模块已显示', 'success');
            this.addLogEntry('请选择模型和语言，然后点击"开始提取字幕"', 'info');
        }
    }
    
    async loadModelStatusAndUpdateSelect() {
        try {
            const response = await fetch('/api/whisper-info');
            const data = await response.json();
            
            if (data.success && data.installed_models) {
                const modelSelect = document.getElementById('whisper-model-select');
                if (!modelSelect) return;
                
                // 保存当前选中的值
                const currentValue = modelSelect.value;
                
                // 清空并重新填充选项
                modelSelect.innerHTML = '';
                
                // 模型显示名称映射
                const modelDisplayNames = {
                    'tiny': 'Tiny (39M参数) - 极速模式',
                    'base': 'Base (74M参数) - 推荐',
                    'small': 'Small (244M参数) - 高精度',
                    'medium': 'Medium (769M参数) - 专业级',
                    'large': 'Large (1550M参数) - 最高精度',
                    'large-v3-turbo': 'Large-v3-Turbo (779M参数) - 最新版'
                };
                
                // 为每个模型创建选项
                data.installed_models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.name;
                    
                    // 基础显示名称
                    let displayName = modelDisplayNames[model.name] || model.name;
                    
                    // 添加安装状态标识
                    if (model.status === 'installed') {
                        displayName += ' ✓ 已安装';
                        option.style.color = '#28a745';
                        option.style.fontWeight = '500';
                    } else {
                        displayName += ' (需下载)';
                        option.style.color = '#6c757d';
                    }
                    
                    option.textContent = displayName;
                    
                    // 添加数据属性
                    option.dataset.status = model.status;
                    option.dataset.size = model.expected_size_mb;
                    
                    modelSelect.appendChild(option);
                });
                
                // 恢复之前选中的值，如果不存在则选择第一个已安装的模型
                if (currentValue && modelSelect.querySelector(`option[value="${currentValue}"]`)) {
                    modelSelect.value = currentValue;
                } else {
                    // 选择第一个已安装的模型，如果没有则选择base
                    const installedOption = Array.from(modelSelect.options).find(opt => opt.dataset.status === 'installed');
                    if (installedOption) {
                        modelSelect.value = installedOption.value;
                    } else {
                        modelSelect.value = 'base';
                    }
                }
                
                // 更新已安装模型列表
                this.updateInstalledModelsList(data.installed_models);
                
                console.log('模型状态已更新到下拉框');
            }
        } catch (error) {
            console.error('加载模型状态失败:', error);
        }
    }
    
    updateInstalledModelsList(models) {
        console.log('updateInstalledModelsList 被调用，模型数据:', models);
        
        const section = document.getElementById('installed-models-section');
        const listContainer = document.getElementById('installed-models-list');
        
        console.log('section元素:', section);
        console.log('listContainer元素:', listContainer);
        
        if (!section || !listContainer) {
            console.error('找不到已安装模型的显示元素');
            return;
        }
        
        // 筛选已安装的模型
        const installedModels = models.filter(m => m.status === 'installed');
        console.log('已安装的模型:', installedModels);
        
        if (installedModels.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center text-muted py-2">
                    <i class="bi bi-inbox me-2"></i>
                    暂无已安装的模型
                </div>
            `;
            section.style.display = 'block';
            return;
        }
        
        // 显示已安装的模型
        let html = '';
        installedModels.forEach(model => {
            const location = model.primary_location;
            const sizeMB = location ? location.size_mb : model.expected_size_mb;
            const cacheName = location ? location.cache_name : '未知';
            const path = location ? location.path : '未知';
            
            // 简化路径显示 - 替换用户主目录为~
            let shortPath = path;
            // 尝试替换常见的用户主目录路径
            if (path.includes('/Users/')) {
                shortPath = path.replace(/\/Users\/[^\/]+/, '~');
            } else if (path.includes('/home/')) {
                shortPath = path.replace(/\/home\/[^\/]+/, '~');
            }
            
            // 如果路径太长，截断显示
            if (shortPath.length > 50) {
                shortPath = shortPath.substring(0, 47) + '...';
            }
            
            html += `
                <div class="model-item mb-2 p-2 bg-white rounded border">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="fw-bold text-success">
                                <i class="bi bi-check-circle-fill me-1"></i>
                                ${model.name.toUpperCase()}
                            </div>
                            <div class="text-muted" style="font-size: 0.75rem;">
                                <i class="bi bi-cpu me-1"></i>
                                参数量: ${model.parameters || '未知'}
                            </div>
                            <div class="text-muted" style="font-size: 0.75rem;">
                                <i class="bi bi-hdd me-1"></i>
                                文件大小: ${sizeMB} MB
                            </div>
                        </div>
                        <div class="text-end">
                            <span class="badge bg-success" style="font-size: 0.7rem;">
                                ${cacheName}
                            </span>
                        </div>
                    </div>
                    <div class="mt-1" style="font-size: 0.7rem;">
                        <i class="bi bi-folder2 me-1 text-muted"></i>
                        <span class="text-muted" title="${path}">${shortPath}</span>
                        <button class="btn btn-link btn-sm p-0 ms-1" onclick="navigator.clipboard.writeText('${path}'); this.innerHTML='<i class=\\'bi bi-check\\'></i>'; setTimeout(() => this.innerHTML='<i class=\\'bi bi-clipboard\\'></i>', 1000);" title="复制路径">
                            <i class="bi bi-clipboard"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        
        listContainer.innerHTML = html;
        section.style.display = 'block';
    }

    async loadWhisperInfo() {
        try {
            const response = await fetch('/api/whisper-info');
            const data = await response.json();
            
            if (data.success) {
                // 更新系统信息
                const whisperVersion = document.getElementById('whisper-version');
                const gpuStatus = document.getElementById('gpu-status');
                const modelCachePath = document.getElementById('model-cache-path');
                
                if (whisperVersion) {
                    whisperVersion.textContent = data.whisper_version;
                }
                
                if (gpuStatus) {
                    if (data.gpu_available) {
                        gpuStatus.innerHTML = `<span class="text-success">可用 (${data.gpu_device || 'GPU'})</span>`;
                    } else {
                        gpuStatus.innerHTML = '<span class="text-warning">不可用 (使用CPU)</span>';
                    }
                }
                
                if (modelCachePath) {
                    // 显示多个缓存路径
                    const cacheDirs = data.cache_dirs || [['默认', data.cache_dir]];
                    const pathsText = cacheDirs.map(([name, path]) => `${name}: ${path}`).join('\n');
                    modelCachePath.textContent = cacheDirs.length > 1 ? `${cacheDirs.length}个位置` : cacheDirs[0][1];
                    modelCachePath.title = pathsText;
                }
                
                // 检查whisper-cpp可用性（可选功能）
                const cppEngineOption = document.getElementById('cpp-engine-option');
                
                if (cppEngineOption && data.whisper_cpp_available) {
                    cppEngineOption.disabled = false;
                    cppEngineOption.textContent = 'Whisper-CPP (可用)';
                    this.addLogEntry(`检测到whisper-cpp: ${data.whisper_cpp_path}`, 'info');
                }
                
                // 更新已安装模型列表
                this.updateInstalledModels(data.installed_models);
                
                // 记录到日志
                this.addLogEntry(`Whisper系统信息加载完成`, 'info');
                this.addLogEntry(`版本: ${data.whisper_version}`, 'info');
                this.addLogEntry(`GPU加速: ${data.gpu_available ? '可用' : '不可用'}`, 'info');
                
                // 记录找到的模型位置
                if (data.cache_dirs) {
                    data.cache_dirs.forEach(([name, path]) => {
                        this.addLogEntry(`模型位置 (${name}): ${path}`, 'info');
                    });
                }
                
                // 统计已安装的模型
                const installedCount = data.installed_models.filter(m => m.status === 'installed').length;
                this.addLogEntry(`已安装模型: ${installedCount}/${data.installed_models.length}`, 'info');
                
            } else {
                console.error('获取Whisper信息失败:', data.error);
                this.addLogEntry(`获取Whisper信息失败: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('加载Whisper信息失败:', error);
            this.addLogEntry(`加载Whisper信息失败: ${error.message}`, 'error');
        }
    }

    updateInstalledModels(models) {
        const installedModelsDiv = document.getElementById('installed-models');
        if (!installedModelsDiv) return;
        
        let html = '';
        models.forEach(model => {
            if (model.status === 'installed') {
                // 显示主要位置的信息
                const primaryLocation = model.primary_location;
                const sizeStr = this.formatFileSize(primaryLocation.size);
                const locationName = primaryLocation.cache_name;
                
                html += `
                    <div class="mb-2">
                        <div class="d-flex justify-content-between align-items-center">
                            <span class="text-success">
                                <i class="bi bi-check-circle me-1"></i>
                                ${model.name.charAt(0).toUpperCase() + model.name.slice(1)}
                            </span>
                            <span class="text-muted">${sizeStr}</span>
                        </div>
                        <div class="small text-muted ms-3">
                            <i class="bi bi-folder me-1"></i>
                            ${locationName}
                        </div>
                `;
                
                // 如果有多个位置，显示数量
                if (model.locations && model.locations.length > 1) {
                    html += `
                        <div class="small text-info ms-3">
                            <i class="bi bi-info-circle me-1"></i>
                            找到 ${model.locations.length} 个版本
                        </div>
                    `;
                }
                
                html += '</div>';
            } else {
                html += `
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span class="text-muted">
                            <i class="bi bi-download me-1"></i>
                            ${model.name.charAt(0).toUpperCase() + model.name.slice(1)}
                        </span>
                        <span class="text-muted">未安装</span>
                    </div>
                `;
            }
        });
        
        if (html === '') {
            html = '<div class="text-muted">未检测到已安装的模型</div>';
        }
        
        installedModelsDiv.innerHTML = html;
    }

    updateEngineDescription() {
        const engineSelect = document.getElementById('whisper-engine-select');
        const engineDescription = document.getElementById('engine-description');
        
        if (!engineSelect || !engineDescription) return;
        
        const selectedEngine = engineSelect.value;
        
        if (selectedEngine === 'python') {
            engineDescription.innerHTML = `
                <i class="bi bi-info-circle me-1"></i>
                Python Whisper: 功能完整，支持GPU加速，自动下载模型
            `;
        } else if (selectedEngine === 'cpp') {
            engineDescription.innerHTML = `
                <i class="bi bi-info-circle me-1"></i>
                Whisper-CPP: 速度更快，使用已有模型，无需下载
            `;
        }
        
        // 记录引擎选择
        if (selectedEngine === 'cpp') {
            this.addLogEntry(`选择处理引擎: Whisper-CPP`, 'info');
        } else {
            this.addLogEntry(`选择处理引擎: Python Whisper`, 'info');
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async updateModelInfo() {
        const modelSelect = document.getElementById('whisper-model-select');
        const modelInfoDisplay = document.getElementById('model-info-display');
        
        if (!modelSelect || !modelInfoDisplay) return;
        
        const selectedModel = modelSelect.value;
        this.addLogEntry(`选择了模型: ${selectedModel}`, 'info');
        
        // 显示加载状态
        modelInfoDisplay.innerHTML = '<div class="spinner-border spinner-border-sm me-2"></div>加载模型信息...';
        
        try {
            // 获取模型信息
            const response = await fetch('/api/whisper-model-info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    model_size: selectedModel
                })
            });
            
            if (!response.ok) {
                throw new Error('获取模型信息失败');
            }
            
            const data = await response.json();
            
            if (data.success) {
                const modelInfo = data.model_info;
                
                // 构建模型信息显示
                let infoHtml = '<div class="model-info-content">';
                infoHtml += `<div class="info-item"><strong>模型:</strong> ${modelInfo.model_name || selectedModel}</div>`;
                
                if (modelInfo.model_location) {
                    infoHtml += `<div class="info-item"><strong>位置:</strong> ${modelInfo.model_location}</div>`;
                }
                
                if (modelInfo.model_source) {
                    infoHtml += `<div class="info-item"><strong>来源:</strong> ${modelInfo.model_source}</div>`;
                }
                
                if (modelInfo.model_size_mb) {
                    infoHtml += `<div class="info-item"><strong>大小:</strong> ${modelInfo.model_size_mb} MB</div>`;
                }
                
                if (modelInfo.parameters) {
                    infoHtml += `<div class="info-item"><strong>参数量:</strong> ${(modelInfo.parameters / 1000000).toFixed(1)}M</div>`;
                }
                
                if (modelInfo.device) {
                    infoHtml += `<div class="info-item"><strong>设备:</strong> ${modelInfo.device}</div>`;
                }
                
                if (modelInfo.performance) {
                    infoHtml += `<div class="info-item"><strong>性能:</strong> ${modelInfo.performance}</div>`;
                }
                
                infoHtml += '</div>';
                
                modelInfoDisplay.innerHTML = infoHtml;
                
                // 记录模型信息到日志
                this.addLogEntry(`模型信息: ${modelInfo.model_name || selectedModel}`, 'info');
                if (modelInfo.model_location) {
                    this.addLogEntry(`模型位置: ${modelInfo.model_location}`, 'info');
                }
                if (modelInfo.model_source) {
                    this.addLogEntry(`模型来源: ${modelInfo.model_source}`, 'info');
                }
                if (modelInfo.model_size_mb) {
                    this.addLogEntry(`模型大小: ${modelInfo.model_size_mb} MB`, 'info');
                }
                if (modelInfo.parameters) {
                    this.addLogEntry(`模型参数量: ${(modelInfo.parameters / 1000000).toFixed(1)}M`, 'info');
                }
                if (modelInfo.device) {
                    this.addLogEntry(`使用设备: ${modelInfo.device}`, 'info');
                }
                if (modelInfo.performance) {
                    this.addLogEntry(`模型性能: ${modelInfo.performance}`, 'info');
                }
            } else {
                throw new Error(data.error || '获取模型信息失败');
            }
        } catch (error) {
            console.error('获取模型信息失败:', error);
            modelInfoDisplay.innerHTML = `<div class="text-danger">无法获取模型信息: ${error.message}</div>`;
            this.addLogEntry(`获取模型信息失败: ${error.message}`, 'error');
        }
    }

    /**
     * 提取字幕的入口方法
     * 验证输入并调用extractSubtitleFromAudio()
     */
    async extractSubtitle() {
        console.log('=== extractSubtitle 方法被调用 ===');
        
        // 验证音频文件是否已上传
        if (!this.uploadedFiles || !this.uploadedFiles.audio) {
            this.showError('请先上传音频文件');
            this.addLogEntry('提取失败: 未上传音频文件', 'error');
            return;
        }
        
        // 验证模型是否已选择
        const modelSelect = document.getElementById('whisper-model-select');
        if (!modelSelect || !modelSelect.value) {
            this.showError('请选择Whisper模型');
            this.addLogEntry('提取失败: 未选择模型', 'error');
            return;
        }
        
        // 验证语言是否已选择
        const languageSelect = document.getElementById('audio-language-select');
        if (!languageSelect || !languageSelect.value) {
            this.showError('请选择音频语言');
            this.addLogEntry('提取失败: 未选择语言', 'error');
            return;
        }
        
        // 检查是否应该显示下载进度
        const selectedModel = modelSelect.value;
        const downloadProgressDiv = document.getElementById('model-download-progress');
        
        if (downloadProgressDiv) {
            if (this.shouldShowDownloadProgress(selectedModel)) {
                // 模型未安装，显示下载进度区域
                downloadProgressDiv.style.display = 'block';
                console.log(`模型 ${selectedModel} 未安装，显示下载进度`);
            } else {
                // 模型已安装，隐藏下载进度区域
                downloadProgressDiv.style.display = 'none';
                console.log(`模型 ${selectedModel} 已安装，隐藏下载进度`);
            }
        }
        
        // 调用实际的提取方法
        await this.extractSubtitleFromAudio();
    }

    /**
     * 设置提取按钮的状态
     * @param {boolean} enabled - 是否启用按钮
     * @param {string} text - 按钮文本
     */
    setExtractButtonState(enabled, text) {
        const extractBtn = document.getElementById('extract-subtitle-btn');
        if (!extractBtn) return;
        
        extractBtn.disabled = !enabled;
        
        if (enabled) {
            // 启用状态：显示正常图标
            extractBtn.innerHTML = `<i class="bi bi-play-circle me-1"></i>${text}`;
        } else {
            // 禁用状态：显示loading spinner
            extractBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>${text}`;
        }
    }

    /**
     * 显示提取状态消息
     * @param {string} message - 状态消息
     * @param {string} type - 消息类型 ('info', 'success', 'warning', 'error')
     */
    showExtractionStatus(message, type = 'info') {
        const statusDiv = document.getElementById('extract-subtitle-status');
        if (!statusDiv) return;
        
        // 定义不同类型的样式和图标
        const typeConfig = {
            'info': {
                alertClass: 'alert-info',
                icon: 'bi-info-circle',
                badgeClass: 'bg-info'
            },
            'success': {
                alertClass: 'alert-success',
                icon: 'bi-check-circle',
                badgeClass: 'bg-success'
            },
            'warning': {
                alertClass: 'alert-warning',
                icon: 'bi-exclamation-triangle',
                badgeClass: 'bg-warning text-dark'
            },
            'error': {
                alertClass: 'alert-danger',
                icon: 'bi-x-circle',
                badgeClass: 'bg-danger'
            }
        };
        
        const config = typeConfig[type] || typeConfig['info'];
        
        // 显示状态消息
        statusDiv.style.display = 'block';
        statusDiv.innerHTML = `
            <div class="alert ${config.alertClass} mb-0">
                <i class="${config.icon} me-2"></i>${message}
            </div>
        `;
        
        // 成功消息3秒后自动隐藏
        if (type === 'success') {
            setTimeout(() => {
                if (statusDiv.style.display !== 'none') {
                    statusDiv.style.display = 'none';
                }
            }, 3000);
        }
    }

    /**
     * 获取模型状态并缓存
     * @returns {Promise<Object>} 模型状态数据
     */
    async fetchModelStatus() {
        try {
            // 检查缓存是否有效（5分钟内）
            const now = Date.now();
            if (this.modelStatusCache && this.lastUpdateTime && (now - this.lastUpdateTime < 5 * 60 * 1000)) {
                console.log('使用缓存的模型状态');
                return this.modelStatusCache;
            }
            
            console.log('从服务器获取模型状态');
            const response = await fetch('/api/whisper-info');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                // 缓存模型状态
                this.modelStatusCache = data;
                this.lastUpdateTime = now;
                console.log('模型状态已缓存');
                return data;
            } else {
                throw new Error('获取模型状态失败');
            }
        } catch (error) {
            console.error('获取模型状态失败:', error);
            this.addLogEntry(`获取模型状态失败: ${error.message}`, 'error');
            return null;
        }
    }

    /**
     * 获取特定模型的状态
     * @param {string} modelName - 模型名称
     * @returns {Object|null} 模型状态对象
     */
    getModelStatus(modelName) {
        if (!this.modelStatusCache || !this.modelStatusCache.installed_models) {
            return null;
        }
        
        return this.modelStatusCache.installed_models.find(m => m.name === modelName);
    }

    /**
     * 检查模型是否已安装
     * @param {string} modelName - 模型名称
     * @returns {boolean} 是否已安装
     */
    isModelInstalled(modelName) {
        const modelStatus = this.getModelStatus(modelName);
        return modelStatus && modelStatus.status === 'installed';
    }

    /**
     * 更新模型选择下拉框的UI
     * 调用现有的loadModelStatusAndUpdateSelect方法
     */
    async updateModelSelectUI() {
        await this.loadModelStatusAndUpdateSelect();
    }

    /**
     * 判断是否应该显示下载进度
     * @param {string} modelSize - 模型大小
     * @returns {boolean} 是否应该显示下载进度
     */
    shouldShowDownloadProgress(modelSize) {
        // 如果模型已安装，不显示下载进度
        if (this.isModelInstalled(modelSize)) {
            console.log(`模型 ${modelSize} 已安装，不显示下载进度`);
            return false;
        }
        
        console.log(`模型 ${modelSize} 未安装，需要显示下载进度`);
        return true;
    }

    /**
     * 处理字幕提取错误
     * @param {Error|Object} error - 错误对象
     * @param {number} statusCode - HTTP状态码（可选）
     */
    handleExtractionError(error, statusCode = null) {
        console.error('处理提取错误:', error, '状态码:', statusCode);
        
        let errorMessage = '提取字幕失败';
        let errorDetails = '';
        
        // 根据状态码或错误类型生成友好的错误消息
        if (statusCode === 404) {
            errorMessage = '音频文件未找到';
            errorDetails = '请重新上传音频文件';
        } else if (statusCode === 400) {
            errorMessage = '请求参数错误';
            errorDetails = error.message || '请检查输入参数';
        } else if (statusCode === 500) {
            errorMessage = '服务器错误';
            errorDetails = '请稍后重试或联系管理员';
        } else if (error.message && error.message.includes('网络')) {
            errorMessage = '网络连接失败';
            errorDetails = '请检查网络连接后重试';
        } else if (error.message && error.message.includes('timeout')) {
            errorMessage = '请求超时';
            errorDetails = '服务器响应时间过长，请稍后重试';
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        // 显示错误消息
        this.showExtractionStatus(`${errorMessage}${errorDetails ? ': ' + errorDetails : ''}`, 'error');
        this.addLogEntry(`提取失败: ${errorMessage}`, 'error');
        if (errorDetails) {
            this.addLogEntry(`详情: ${errorDetails}`, 'error');
        }
        
        // 重新启用提取按钮
        this.setExtractButtonState(true, '开始提取字幕');
        
        // 隐藏下载进度
        const downloadProgressDiv = document.getElementById('model-download-progress');
        if (downloadProgressDiv) {
            downloadProgressDiv.style.display = 'none';
        }
    }

    async extractSubtitleFromAudio() {
        console.log('=== extractSubtitleFromAudio 方法被调用 ===');
        this.isExtractingSubtitle = true;
        console.log('当前上传的文件:', this.uploadedFiles);
        
        // 检查是否已上传音频文件
        if (!this.uploadedFiles.audio) {
            this.showError('请先上传音频文件');
            return;
        }

        // 获取提取字幕按钮和状态显示元素
        const extractBtn = document.getElementById('extract-subtitle-btn');
        const statusDiv = document.getElementById('extract-subtitle-status');
        const statusText = document.getElementById('extract-status-text');
        const modelSelect = document.getElementById('whisper-model-select');
        const languageSelect = document.getElementById('audio-language-select');
        const engineSelect = document.getElementById('whisper-engine-select');
        
        // 获取模型下载进度元素
        const downloadProgressDiv = document.getElementById('model-download-progress');
        const downloadTitle = document.getElementById('model-download-title');
        const downloadProgressBar = document.getElementById('model-download-progress-bar');
        const downloadPercent = document.getElementById('model-download-percent');
        const downloadSize = document.getElementById('model-download-size');
        const downloadSpeed = document.getElementById('model-download-speed');
        
        // 获取选择的模型和语言（固定使用Python Whisper）
        const selectedModel = modelSelect ? modelSelect.value : 'base';
        const selectedLanguage = languageSelect ? languageSelect.value : 'zh';
        const selectedEngine = 'python';
        
        // 初始化状态显示
        if (statusDiv) {
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = `<div class="d-flex align-items-center"><span class="badge bg-info me-2">初始化</span><span>正在准备提取...</span></div>`;
        }
        
        // 设置WebSocket监听模型下载进度
        const modelDownloadHandler = (data) => {
            console.log('收到模型下载进度:', data);
            
            // 检查是否是当前模型的进度
            if (data.model_size && data.model_size !== selectedModel) {
                return;
            }
            
            // 显示下载进度
            downloadProgressDiv.style.display = 'block';
            
            if (data.status === 'starting') {
                downloadTitle.textContent = `正在下载模型: ${data.model_size?.toUpperCase() || selectedModel}`;
                downloadProgressBar.style.width = '10%';
                downloadProgressBar.setAttribute('aria-valuenow', '10');
                downloadPercent.textContent = '10%';
                
                // 显示设备信息和下载链接
                let infoText = '准备下载...';
                if (data.device && data.compute_type) {
                    infoText = `使用设备: ${data.device.toUpperCase()}, 计算类型: ${data.compute_type}`;
                }
                downloadSize.textContent = infoText;
                
                // 显示下载链接
                if (data.download_url) {
                    downloadSpeed.innerHTML = `<a href="${data.download_url}" target="_blank" class="text-info">
                        <i class="bi bi-link-45deg me-1"></i>查看下载源
                    </a>`;
                } else {
                    downloadSpeed.textContent = '初始化中...';
                }
            } else if (data.status === 'progress') {
                downloadTitle.textContent = `正在下载模型: ${data.model_size?.toUpperCase() || selectedModel}`;
                const progress = data.progress || 0;
                downloadProgressBar.style.width = `${progress}%`;
                downloadProgressBar.setAttribute('aria-valuenow', progress);
                downloadPercent.textContent = `${progress}%`;
                
                // 如果有下载大小信息，显示它
                if (data.downloaded_size && data.total_size) {
                    const downloadedMB = (data.downloaded_size / (1024 * 1024)).toFixed(2);
                    const totalMB = (data.total_size / (1024 * 1024)).toFixed(2);
                    downloadSize.textContent = `${downloadedMB} MB / ${totalMB} MB`;
                } else {
                    downloadSize.textContent = data.message || `下载进度: ${progress}%`;
                }
                
                // 显示下载速度，如果没有则显示设备信息
                if (data.download_speed) {
                    const speedKB = (data.download_speed / 1024).toFixed(2);
                    downloadSpeed.textContent = `${speedKB} KB/s`;
                } else if (data.device && data.compute_type) {
                    // 如果没有下载速度但有设备信息，显示设备信息
                    downloadSpeed.textContent = `${data.device.toUpperCase()} | ${data.compute_type}`;
                } else {
                    downloadSpeed.textContent = '';
                }
            } else if (data.status === 'completed') {
                downloadTitle.textContent = `模型 ${data.model_size?.toUpperCase() || selectedModel} 下载完成`;
                downloadProgressBar.style.width = '100%';
                downloadProgressBar.setAttribute('aria-valuenow', '100');
                downloadPercent.textContent = '100%';
                
                // 显示设备信息
                let infoText = '下载完成';
                if (data.device && data.compute_type) {
                    infoText = `使用设备: ${data.device.toUpperCase()}, 计算类型: ${data.compute_type}`;
                }
                downloadSize.textContent = infoText;
                
                // 显示下载链接
                if (data.download_url) {
                    downloadSpeed.innerHTML = `<a href="${data.download_url}" target="_blank" class="text-success">
                        <i class="bi bi-check-circle me-1"></i>下载源
                    </a>`;
                } else {
                    downloadSpeed.textContent = '';
                }
                
                // 3秒后隐藏进度条
                setTimeout(() => {
                    downloadProgressDiv.style.display = 'none';
                }, 3000);
            } else if (data.status === 'error') {
                downloadTitle.textContent = `模型 ${data.model_size?.toUpperCase() || selectedModel} 下载失败`;
                downloadProgressBar.className = 'progress-bar bg-danger';
                
                // 创建错误消息和重试按钮
                let errorContent = `<div class="d-flex justify-content-between align-items-center">
                    <div>
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        ${data.message || '未知错误'}
                    </div>`;
                
                // 如果可以重试，添加重试按钮
                if (data.can_retry !== false) {
                    errorContent += `<button class="btn btn-sm btn-outline-primary retry-download-btn ms-2" 
                        data-model="${data.model_size || selectedModel}">
                        <i class="bi bi-arrow-clockwise me-1"></i>重试
                    </button>`;
                }
                
                errorContent += `</div>`;
                
                // 如果有错误类型，显示对应的图标和操作
                if (data.error_type) {
                    let iconClass = '';
                    let actionText = '';
                    switch(data.error_type) {
                        case 'server_error':
                            iconClass = 'bi-server';
                            actionText = '服务器错误';
                            break;
                        case 'network_error':
                            iconClass = 'bi-wifi-off';
                            actionText = '网络错误';
                            break;
                        case 'disk_error':
                            iconClass = 'bi-hdd';
                            actionText = '磁盘空间不足';
                            break;
                        case 'model_corrupted':
                            iconClass = 'bi-file-earmark-x';
                            actionText = '模型文件损坏';
                            // 添加删除损坏模型的按钮
                            if (data.model_path) {
                                errorContent = `<div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <i class="${iconClass} me-2"></i>
                                        ${data.message || '模型文件损坏'}
                                    </div>
                                    <div>
                                        <button class="btn btn-sm btn-outline-danger delete-model-btn ms-2" 
                                            data-model-path="${data.model_path}">
                                            <i class="bi bi-trash me-1"></i>删除损坏模型
                                        </button>`;
                                if (data.can_retry !== false) {
                                    errorContent += `<button class="btn btn-sm btn-outline-primary retry-download-btn ms-2" 
                                        data-model="${data.model_size || selectedModel}">
                                        <i class="bi bi-arrow-clockwise me-1"></i>重新下载
                                    </button>`;
                                }
                                errorContent += `</div></div>`;
                            }
                            break;
                        default:
                            iconClass = 'bi-exclamation-circle';
                            actionText = '未知错误';
                    }
                    if (data.error_type !== 'model_corrupted') {
                        errorContent = errorContent.replace('bi-exclamation-triangle', iconClass);
                    }
                }
                
                downloadSize.innerHTML = errorContent;
                downloadSpeed.textContent = '';
                
                // 添加重试按钮和删除模型按钮事件监听器
                if (data.can_retry !== false || data.error_type === 'model_corrupted') {
                    setTimeout(() => {
                        const retryBtn = document.querySelector('.retry-download-btn');
                        if (retryBtn) {
                            retryBtn.addEventListener('click', () => {
                                const modelToRetry = retryBtn.getAttribute('data-model');
                                this.downloadModelDirectly(modelToRetry, () => {
                                    // 下载完成后重新尝试字幕提取
                                    this.extractSubtitleFromAudio();
                                });
                            });
                        }
                        
                        const deleteBtn = document.querySelector('.delete-model-btn');
                        if (deleteBtn) {
                            deleteBtn.addEventListener('click', async () => {
                                const modelPath = deleteBtn.getAttribute('data-model-path');
                                try {
                                    deleteBtn.disabled = true;
                                    deleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>删除中...';
                                    
                                    const response = await fetch('/api/delete-whisper-model', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json',
                                        },
                                        body: JSON.stringify({ model_path: modelPath })
                                    });
                                    
                                    const result = await response.json();
                                    if (response.ok && result.success) {
                                        this.addLogEntry(`损坏模型已删除: ${modelPath}`, 'success');
                                        // 隐藏删除按钮，只显示重试按钮
                                        deleteBtn.parentElement.style.display = 'none';
                                    } else {
                                        this.addLogEntry(`删除模型失败: ${result.error || '未知错误'}`, 'error');
                                        deleteBtn.disabled = false;
                                        deleteBtn.innerHTML = '<i class="bi bi-trash me-1"></i>删除损坏模型';
                                    }
                                } catch (error) {
                                    this.addLogEntry(`删除模型失败: ${error.message}`, 'error');
                                    deleteBtn.disabled = false;
                                    deleteBtn.innerHTML = '<i class="bi bi-trash me-1"></i>删除损坏模型';
                                }
                            });
                        }
                    }, 100);
                }
            }
        };
        
        // 添加WebSocket监听器
        if (this.socket) {
            this.socket.on('model_download_progress', modelDownloadHandler);
        }
        
        // 显示加载状态
        extractBtn.disabled = true;
        extractBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>提取中...';
        statusDiv.style.display = 'block';
        
        // 先检查模型是否已安装，再决定是否显示下载进度UI
        const checkModelResponse = await fetch(`/api/check-model-exists?model_size=${selectedModel}`);
        let modelExists = false;
        
        if (checkModelResponse.ok) {
            const modelData = await checkModelResponse.json();
            modelExists = modelData.exists;
            console.log(`模型 ${selectedModel} 是否存在:`, modelExists);
        }
        
        // 只有当模型不存在时才显示下载进度UI
        if (!modelExists) {
            // 显示模型下载提示（如果是首次使用）
            downloadProgressDiv.style.display = 'block';
            downloadTitle.textContent = `正在准备模型: ${selectedModel}`;
            downloadProgressBar.style.width = '0%';
            downloadPercent.textContent = '准备中...';
            downloadSize.textContent = '首次使用会自动下载模型';
            downloadSpeed.textContent = '正在初始化...';
        } else {
            // 模型已存在，显示加载状态但不显示下载进度
            downloadProgressDiv.style.display = 'none';
        }
        
        if (statusText) {
            statusText.textContent = `正在使用 Python Whisper (${selectedModel.toUpperCase()}) 提取字幕...`;
        }

        try {
            // 获取当前书名
            const bookName = this.getCurrentBookName() || "默认书籍";
            
            // 记录开始提取的日志
            this.addLogEntry(`开始提取字幕`, 'info');
            this.addLogEntry(`处理引擎: Python Whisper`, 'info');
            this.addLogEntry(`使用模型: ${selectedModel.toUpperCase()}`, 'info');
            this.addLogEntry(`音频语言: ${selectedLanguage === 'auto' ? '自动检测' : selectedLanguage}`, 'info');
            this.addLogEntry(`音频文件: ${this.uploadedFiles.audio.name}`, 'info');

            // 使用Python Whisper API
            const apiEndpoint = '/api/extract-subtitle-from-audio';
            
            const requestData = {
                book_name: bookName,
                audio_file_key: this.uploadedFiles.audio.key || this.uploadedFiles.audio.file_key || this.uploadedFiles.audio.name,
                model_size: selectedModel,
                language: selectedLanguage
            };
            
            console.log('发送请求数据:', requestData);
            this.addLogEntry(`请求数据: ${JSON.stringify(requestData)}`, 'debug');
            
            const response = await fetch(apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            console.log('响应状态:', response.status, response.statusText);
            this.addLogEntry(`响应状态: ${response.status} ${response.statusText}`, 'debug');

            // 检查响应是否为JSON
            const contentType = response.headers.get('content-type');
            
            if (!contentType || !contentType.includes('application/json')) {
                const responseText = await response.text();
                console.error('响应不是JSON格式:', responseText);
                this.addLogEntry(`响应内容: ${responseText}`, 'error');
                throw new Error('服务器返回了非JSON格式的响应');
            }
            
            const data = await response.json();
            console.log('响应数据:', data);
            this.addLogEntry(`响应数据: ${JSON.stringify(data)}`, 'debug');

            if (response.ok) {
                // 检查是否覆盖了现有文件
                const overwriteWarning = data.overwritten ? 
                    '<br><span class="text-warning"><i class="bi bi-exclamation-triangle me-1"></i>已覆盖同名字幕文件</span>' : '';
                
                // 提取成功
                const engine = data.model_info?.engine || 'Python Whisper';
                const engineDisplay = engine === 'whisper-cpp' ? 'Whisper-CPP' : 'Python Whisper';
                
                statusDiv.innerHTML = `<div class="alert alert-success">
                    <i class="bi bi-check-circle me-2"></i>
                    字幕提取成功！文件已保存为: ${data.subtitle_filename}${overwriteWarning}
                    <br><small class="text-muted">
                        保存位置: ${data.subtitle_path || '字幕文件目录'}<br>
                        引擎: ${engineDisplay} | 
                        检测语言: ${data.detected_language || '未知'} | 
                        字幕片段: ${data.segment_count || 0} 个 | 
                        使用模型: ${selectedModel.toUpperCase()} | 
                        设备: ${data.model_info?.device || '未知'}
                    </small>
                </div>`;
                
                // 更新字幕文件信息
                this.uploadedFiles.subs = {
                    name: data.subtitle_filename,
                    filename: data.subtitle_filename,
                    key: data.subtitle_key,
                    file_key: data.subtitle_key,
                    size: data.size
                };
                
                // 更新字幕上传区域
                this.updateUploadArea(this.subsUploadArea, 'subs', data.subtitle_filename, true);
                
                // 记录成功日志
                this.addLogEntry(`字幕提取成功: ${data.subtitle_filename}`, 'success');
                if (data.subtitle_path) {
                    this.addLogEntry(`保存位置: ${data.subtitle_path}`, 'info');
                }
                if (data.overwritten) {
                    this.addLogEntry(`⚠ 已覆盖同名字幕文件`, 'warning');
                }
                this.addLogEntry(`处理引擎: ${engineDisplay}`, 'info');
                this.addLogEntry(`检测到的语言: ${data.detected_language || '未知'}`, 'info');
                this.addLogEntry(`生成字幕片段: ${data.segment_count || 0} 个`, 'info');
                this.addLogEntry(`文件大小: ${this.formatFileSize(data.size)}`, 'info');
                
                if (data.model_info) {
                    this.addLogEntry(`使用设备: ${data.model_info.device}`, 'info');
                    if (data.model_info.model_path) {
                        this.addLogEntry(`模型路径: ${data.model_info.model_path}`, 'info');
                    }
                    if (data.model_info.parameters) {
                        this.addLogEntry(`模型参数量: ${data.model_info.parameters.toLocaleString()}`, 'info');
                    }
                }
                
                // 显示下一区域，但不调用 loadPDFInfo() 避免重置翻页点设置
                this.showNextSection();
                
                // 显示成功消息
                this.showSuccess(data.overwritten ? '字幕提取成功！已覆盖同名文件' : '字幕提取成功！');
            } else {
                // 处理模型未找到的情况
                if (response.status === 404 && data.error === 'model_not_found') {
                    const modelSize = data.model_size || selectedModel;
                    const modelName = modelSize.toUpperCase();
                    
                    this.addLogEntry(`本地未找到模型 ${modelName}，准备提示下载`, 'warning');
                    
                    // 简单的确认对话框
                    const confirmDownload = confirm(`本地未找到模型 ${modelName}，是否下载？\n模型大小: ${this.getModelSizeInfo(modelSize)}`);
                    
                    if (confirmDownload) {
                        this.addLogEntry(`用户确认下载模型 ${modelName}`, 'info');
                        console.log(`用户确认下载模型: ${modelName}`);
                        
                        statusDiv.innerHTML = `<div class="alert alert-info">
                            <i class="bi bi-download me-2"></i>
                            正在下载模型 ${modelName}...
                            <div class="progress mt-2">
                                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                     role="progressbar" style="width: 10%"></div>
                            </div>
                        </div>`;
                        
                        // 直接开始下载，无需复杂的确认对话框
                        this.downloadModelDirectly(modelSize, () => {
                            // 下载完成后重新尝试字幕提取
                            this.extractSubtitleFromAudio();
                        });
                    } else {
                        this.addLogEntry(`用户取消下载模型 ${modelName}`, 'info');
                        statusDiv.innerHTML = `<div class="alert alert-warning">
                            <i class="bi bi-exclamation-triangle me-2"></i>
                            已取消下载模型 ${modelName}
                            <br><small class="text-muted">
                                您可以选择其他已安装的模型或稍后再试
                            </small>
                        </div>`;
                    }
                    return;
                }
                
                // 处理模型损坏的情况
                if (response.status === 400 && data.error === 'model_corrupted') {
                    const modelSize = data.model_size || selectedModel;
                    const modelPath = data.model_path || '';
                    const deleteModal = this.createModelDeleteModal(modelSize, modelPath);
                    document.body.appendChild(deleteModal);
                    deleteModal.modalInstance.show();
                    
                    statusDiv.innerHTML = `<div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        模型 ${modelSize.toUpperCase()} 文件损坏
                        <br><small class="text-muted">
                            模型文件无法正常加载，需要删除并重新下载
                        </small>
                    </div>`;
                    
                    this.addLogEntry(`模型 ${modelSize.toUpperCase()} 文件损坏`, 'error');
                    this.addLogEntry(`模型路径: ${modelPath}`, 'error');
                    this.addLogEntry(`错误详情: ${data.error_details || ''}`, 'error');
                    return;
                }
                
                // 提取失败
                const errorMessage = data.error || data.message || '未知错误';
                const errorDetails = data.details || '';
                console.error('服务器返回错误:', errorMessage);
                console.error('错误详情:', errorDetails);
                this.addLogEntry(`服务器错误: ${errorMessage}`, 'error');
                if (errorDetails) {
                    this.addLogEntry(`错误详情: ${errorDetails}`, 'error');
                }
                throw new Error(errorMessage + (errorDetails ? '\n详情: ' + errorDetails : ''));
            }
        } catch (error) {
            console.error('提取字幕失败:', error);
            
            // 显示详细的错误信息
            const errorHtml = `<div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle me-2"></i>
                <strong>提取失败:</strong> ${error.message}
                <br><small class="text-muted mt-2 d-block">
                    请检查：
                    <ul class="mb-0 mt-1">
                        <li>音频文件是否完整</li>
                        <li>选择的模型是否已下载完成</li>
                        <li>服务器日志中的详细错误信息</li>
                    </ul>
                </small>
            </div>`;
            
            statusDiv.innerHTML = errorHtml;
            this.addLogEntry(`字幕提取失败: ${error.message}`, 'error');
            this.showError(`提取字幕失败: ${error.message}`);
        } finally {
            this.isExtractingSubtitle = false;
            // 移除WebSocket监听器
            if (this.socket) {
                this.socket.off('model_download_progress', modelDownloadHandler);
            }
            
            // 隐藏下载进度
            if (downloadProgressDiv) {
                downloadProgressDiv.style.display = 'none';
            }
            
            // 恢复按钮状态
            extractBtn.disabled = false;
            extractBtn.innerHTML = '<i class="bi bi-magic me-2"></i>开始提取字幕';
        }
    }

    /**
     * 直接下载模型（简化版本）
     * @param {string} modelSize - 模型大小
     * @param {Function} onSuccess - 下载成功回调
     */
    async downloadModelDirectly(modelSize, onSuccess) {
        const modelName = modelSize.toUpperCase();
        
        this.addLogEntry(`开始下载模型 ${modelName}`, 'info');
        console.log(`开始下载模型: ${modelName}`);
        
        // 添加取消下载按钮
        this.addCancelButton(modelSize);
        
        // 设置WebSocket监听器
        const modelDownloadHandler = (data) => {
            console.log('收到模型下载进度:', data);
            this.addLogEntry(`模型下载进度: ${JSON.stringify(data)}`, 'info');
            
            if (data.model_size === modelSize) {
                // 保存download_id
                if (data.download_id) {
                    this.saveCurrentDownloadId(modelSize, data.download_id);
                }
                
                // 更新UI进度条
                this.updateMainDownloadProgress(data);
                
                if (data.status === 'starting') {
                    this.addLogEntry(`开始下载模型 ${modelName}`, 'info');
                } else if (data.status === 'progress') {
                    const progress = data.progress || 0;
                    this.addLogEntry(`下载进度: ${progress}%`, 'info');
                } else if (data.status === 'completed') {
                    this.addLogEntry(`模型 ${modelName} 下载完成`, 'success');
                    
                    // 移除取消按钮
                    this.removeCancelButton(modelSize);
                    
                    // 刷新已安装模型列表
                    this.updateInstalledModelsList();
                    
                    // 移除WebSocket监听器
                    this.socket.off('model_download_progress', modelDownloadHandler);
                    
                    // 调用成功回调
                    if (onSuccess) {
                        onSuccess();
                    }
                } else if (data.status === 'error') {
                    this.addLogEntry(`模型下载失败: ${data.message}`, 'error');
                    
                    // 移除取消按钮
                    this.removeCancelButton(modelSize);
                    
                    // 移除WebSocket监听器
                    this.socket.off('model_download_progress', modelDownloadHandler);
                } else if (data.status === 'cancelled') {
                    this.addLogEntry(`模型 ${modelName} 下载已取消`, 'warning');
                    
                    // 移除取消按钮
                    this.removeCancelButton(modelSize);
                    
                    // 移除WebSocket监听器
                    this.socket.off('model_download_progress', modelDownloadHandler);
                }
            }
        };
        
        // 添加WebSocket监听器
        this.socket.on('model_download_progress', modelDownloadHandler);
        
        try {
            // 发送下载请求
            const response = await fetch('/api/download-whisper-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ model_size: modelSize })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                if (data.already_exists) {
                    this.addLogEntry(`模型 ${modelName} 已存在`, 'info');
                    
                    // 移除取消按钮
                    this.removeCancelButton(modelSize);
                    
                    // 刷新已安装模型列表
                    this.updateInstalledModelsList();
                    
                    // 移除WebSocket监听器
                    this.socket.off('model_download_progress', modelDownloadHandler);
                    
                    // 调用成功回调
                    if (onSuccess) {
                        onSuccess();
                    }
                } else {
                    // 保存download_id
                    if (data.download_id) {
                        this.saveCurrentDownloadId(modelSize, data.download_id);
                    }
                    this.addLogEntry(`已发送下载请求，等待下载完成...`, 'info');
                }
            } else {
                throw new Error(data.error || '下载请求失败');
            }
        } catch (error) {
            console.error('下载请求错误:', error);
            this.addLogEntry(`模型下载失败: ${error.message}`, 'error');
            
            // 移除取消按钮
            this.removeCancelButton(modelSize);
            
            // 移除WebSocket监听器
            this.socket.off('model_download_progress', modelDownloadHandler);
        }
    }

    /**
     * 创建删除损坏模型的模态框
     * @param {string} modelSize - 模型大小
     * @param {string} modelPath - 模型路径
     * @returns {HTMLElement} 模态框元素
     */
    createModelDeleteModal(modelSize, modelPath) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = `model-delete-modal-${modelSize}`;
        modal.setAttribute('tabindex', '-1');
        modal.setAttribute('aria-labelledby', `model-delete-modal-label-${modelSize}`);
        modal.setAttribute('aria-hidden', 'true');
        
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="model-delete-modal-label-${modelSize}">
                            <i class="bi bi-exclamation-triangle me-2"></i>删除损坏的模型 ${modelSize.toUpperCase()}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-danger">
                            <i class="bi bi-exclamation-triangle me-2"></i>
                            模型 ${modelSize.toUpperCase()} 文件已损坏，无法正常使用。
                        </div>
                        
                        <div class="mb-3">
                            <h6>模型信息：</h6>
                            <ul class="list-unstyled">
                                <li><strong>模型名称：</strong>${modelSize.toUpperCase()}</li>
                                <li><strong>模型路径：</strong><code class="text-break">${modelPath}</code></li>
                            </ul>
                        </div>
                        
                        <div class="mb-3">
                            <h6>解决方案：</h6>
                            <p>需要删除损坏的模型文件，然后重新下载。删除操作将：</p>
                            <ul>
                                <li>删除损坏的模型文件</li>
                                <li>释放磁盘空间</li>
                                <li>允许重新下载完整模型</li>
                            </ul>
                        </div>
                        
                        <div id="delete-progress-container-${modelSize}" style="display: none;">
                            <div class="mb-3">
                                <label for="delete-status-${modelSize}" class="form-label">删除进度</label>
                                <div id="delete-status-${modelSize}" class="alert alert-info">
                                    <i class="bi bi-arrow-repeat me-2"></i>正在删除模型文件...
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-danger" id="delete-model-btn-${modelSize}">
                            <i class="bi bi-trash me-2"></i>删除模型
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // 添加删除按钮点击事件
        const deleteBtn = modal.querySelector(`#delete-model-btn-${modelSize}`);
        deleteBtn.addEventListener('click', () => {
            this.deleteModelAndRedownload(modelSize, modal);
        });
        
        // 创建Bootstrap模态框实例
        const modalInstance = new bootstrap.Modal(modal);
        
        // 保存模态框实例到modal元素
        modal.modalInstance = modalInstance;
        
        return modal;
    }
    
    /**
     * 删除损坏的模型并重新下载
     * @param {string} modelSize - 模型大小
     * @param {HTMLElement} deleteModal - 删除模态框元素
     */
    async deleteModelAndRedownload(modelSize, deleteModal) {
        const deleteBtn = deleteModal.querySelector(`#delete-model-btn-${modelSize}`);
        const progressContainer = deleteModal.querySelector(`#delete-progress-container-${modelSize}`);
        const deleteStatus = deleteModal.querySelector(`#delete-status-${modelSize}`);
        
        // 从模态框中获取模型路径
        const modelPathElement = deleteModal.querySelector('code.text-break');
        const modelPath = modelPathElement ? modelPathElement.textContent : '';
        
        // 禁用删除按钮，显示进度
        deleteBtn.disabled = true;
        deleteBtn.innerHTML = '<i class="bi bi-arrow-repeat me-2"></i>删除中...';
        progressContainer.style.display = 'block';
        
        try {
            // 准备请求数据
            const requestData = {
                model_size: modelSize
            };
            
            // 如果有模型路径，添加到请求数据中
            if (modelPath) {
                requestData.model_path = modelPath;
            }
            
            // 调用删除模型API
            const response = await fetch('/api/delete-whisper-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                // 删除成功
                deleteStatus.className = 'alert alert-success';
                deleteStatus.innerHTML = `
                    <i class="bi bi-check-circle me-2"></i>
                    模型删除成功！
                    <br><small>已删除 ${data.deleted_paths.length} 个位置</small>
                `;
                
                this.addLogEntry(`模型 ${modelSize.toUpperCase()} 删除成功`, 'success');
                
                // 延迟后关闭删除模态框并打开下载模态框
                setTimeout(() => {
                    deleteModal.modalInstance.hide();
                    
                    // 创建下载模态框
                    const downloadModal = this.createModelDownloadModal(modelSize);
                    document.body.appendChild(downloadModal);
                    downloadModal.modalInstance.show();
                    
                    this.addLogEntry(`已打开模型 ${modelSize.toUpperCase()} 下载界面`, 'info');
                }, 1500);
            } else {
                // 删除失败
                deleteStatus.className = 'alert alert-danger';
                deleteStatus.innerHTML = `
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    删除失败: ${data.error || '未知错误'}
                `;
                
                this.addLogEntry(`模型 ${modelSize.toUpperCase()} 删除失败: ${data.error || '未知错误'}`, 'error');
                
                // 恢复按钮状态
                deleteBtn.disabled = false;
                deleteBtn.innerHTML = '<i class="bi bi-trash me-2"></i>删除模型';
            }
        } catch (error) {
            // 网络或其他错误
            deleteStatus.className = 'alert alert-danger';
            deleteStatus.innerHTML = `
                <i class="bi bi-exclamation-triangle me-2"></i>
                删除失败: ${error.message}
            `;
            
            this.addLogEntry(`模型 ${modelSize.toUpperCase()} 删除异常: ${error.message}`, 'error');
            
            // 恢复按钮状态
            deleteBtn.disabled = false;
            deleteBtn.innerHTML = '<i class="bi bi-trash me-2"></i>删除模型';
        }
    }

    /**
     * 添加取消下载按钮
     * @param {string} modelSize - 模型大小
     */
    addCancelButton(modelSize) {
        // 检查是否已存在取消按钮
        const existingButton = document.getElementById(`cancel-download-btn-${modelSize}`);
        if (existingButton) {
            existingButton.remove();
        }

        // 创建取消按钮
        const cancelButton = document.createElement('button');
        cancelButton.id = `cancel-download-btn-${modelSize}`;
        cancelButton.className = 'btn btn-warning position-fixed';
        cancelButton.style.cssText = 'top: 20px; right: 20px; z-index: 1050;';
        cancelButton.innerHTML = '<i class="bi bi-x-circle me-2"></i>取消下载';
        
        // 添加点击事件
        cancelButton.addEventListener('click', () => {
            this.cancelDownload(modelSize);
        });
        
        // 添加到页面
        document.body.appendChild(cancelButton);
    }

    /**
     * 移除取消下载按钮
     * @param {string} modelSize - 模型大小
     */
    removeCancelButton(modelSize) {
        const cancelButton = document.getElementById(`cancel-download-btn-${modelSize}`);
        if (cancelButton) {
            cancelButton.remove();
        }
    }

    /**
     * 保存当前下载的download_id
     * @param {string} modelSize - 模型大小
     * @param {string} downloadId - 下载ID
     */
    saveCurrentDownloadId(modelSize, downloadId) {
        if (!this.currentDownloadIds) {
            this.currentDownloadIds = {};
        }
        this.currentDownloadIds[modelSize] = downloadId;
    }

    /**
     * 获取当前下载的download_id
     * @param {string} modelSize - 模型大小
     * @returns {string} 下载ID
     */
    getCurrentDownloadId(modelSize) {
        if (!this.currentDownloadIds) {
            this.currentDownloadIds = {};
        }
        return this.currentDownloadIds[modelSize];
    }

    /**
     * 取消模型下载
     * @param {string} modelSize - 模型大小
     */
    async cancelDownload(modelSize) {
        try {
            // 禁用取消按钮，显示取消中状态
            const cancelButton = document.getElementById(`cancel-download-btn-${modelSize}`);
            if (cancelButton) {
                cancelButton.disabled = true;
                cancelButton.innerHTML = '<i class="bi bi-arrow-repeat me-2"></i>取消中...';
            }

            // 获取当前下载的download_id
            const downloadId = this.getCurrentDownloadId(modelSize);
            
            // 发送取消请求
            const response = await fetch('/api/cancel-download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    model_size: modelSize,
                    download_id: downloadId
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                this.addLogEntry(`已发送取消下载 ${modelSize.toUpperCase()} 的请求`, 'info');
            } else {
                throw new Error(data.error || '取消下载请求失败');
            }
        } catch (error) {
            console.error('取消下载错误:', error);
            this.addLogEntry(`取消下载失败: ${error.message}`, 'error');
            
            // 恢复按钮状态
            const cancelButton = document.getElementById(`cancel-download-btn-${modelSize}`);
            if (cancelButton) {
                cancelButton.disabled = false;
                cancelButton.innerHTML = '<i class="bi bi-x-circle me-2"></i>取消下载';
            }
        }
    }

    createModelDownloadModal(modelSize) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = `model-download-modal-${modelSize}`;
        modal.setAttribute('tabindex', '-1');
        modal.setAttribute('aria-labelledby', `model-download-modal-label-${modelSize}`);
        modal.setAttribute('aria-hidden', 'true');
        
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="model-download-modal-label-${modelSize}">
                            <i class="bi bi-download me-2"></i>下载模型 ${modelSize.toUpperCase()}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-info">
                            <i class="bi bi-info-circle me-2"></i>
                            模型 ${modelSize.toUpperCase()} 未找到，需要下载后才能使用。
                        </div>
                        
                        <div class="mb-3">
                            <h6>模型信息：</h6>
                            <ul class="list-unstyled">
                                <li><strong>模型名称：</strong>${modelSize.toUpperCase()}</li>
                                <li><strong>预计大小：</strong>${this.getModelSizeInfo(modelSize)}</li>
                                <li><strong>预计时间：</strong>取决于网络速度，可能需要几分钟到几十分钟</li>
                            </ul>
                        </div>
                        
                        <div class="mb-3">
                            <h6>下载位置：</h6>
                            <p class="text-muted small">模型将下载到系统缓存目录，具体路径可在下载完成后查看</p>
                        </div>
                        
                        <div id="download-progress-container-${modelSize}" style="display: none;">
                            <div class="mb-3">
                                <label for="download-progress-${modelSize}" class="form-label">下载进度</label>
                                <div class="progress">
                                    <div id="download-progress-${modelSize}" class="progress-bar" role="progressbar" 
                                         style="width: 0%" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                                </div>
                            </div>
                            <div id="download-status-${modelSize}" class="text-muted small"></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" id="download-model-btn-${modelSize}">
                            <i class="bi bi-download me-2"></i>下载模型
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // 添加下载按钮点击事件
        const downloadBtn = modal.querySelector(`#download-model-btn-${modelSize}`);
        downloadBtn.addEventListener('click', () => {
            this.showDownloadConfirmation(modelSize, modal);
        });
        
        // 创建Bootstrap模态框实例
        const modalInstance = new bootstrap.Modal(modal);
        
        // 保存模态框实例到modal元素
        modal.modalInstance = modalInstance;
        
        return modal;
    }
    
    getModelSizeInfo(modelSize) {
        const modelSizes = {
            'tiny': '约 39 MB',
            'base': '约 74 MB',
            'small': '约 244 MB',
            'medium': '约 769 MB',
            'large': '约 1550 MB',
            'large-v3-turbo': '约 1550 MB'
        };
        return modelSizes[modelSize] || '未知大小';
    }
    
    /**
     * 显示下载确认对话框
     * @param {string} modelSize - 模型大小
     * @param {HTMLElement} modal - 模态框元素
     */
    showDownloadConfirmation(modelSize, modal) {
        const downloadBtn = modal.querySelector(`#download-model-btn-${modelSize}`);
        const modalBody = modal.querySelector('.modal-body');
        
        // 保存原始模态框内容
        const originalContent = modalBody.innerHTML;
        
        // 创建确认内容
        const confirmationContent = `
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle me-2"></i>
                <strong>确认下载</strong>
            </div>
            
            <div class="mb-3">
                <h6>您即将下载以下模型：</h6>
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">${modelSize.toUpperCase()}</h5>
                        <p class="card-text">
                            <strong>大小：</strong>${this.getModelSizeInfo(modelSize)}<br>
                            <strong>用途：</strong>用于音频字幕提取<br>
                            <strong>位置：</strong>将下载到系统缓存目录
                        </p>
                    </div>
                </div>
            </div>
            
            <div class="mb-3">
                <h6>下载须知：</h6>
                <ul>
                    <li>下载过程可能需要几分钟到几十分钟，具体取决于您的网络速度</li>
                    <li>下载过程中请勿关闭浏览器或刷新页面</li>
                    <li>模型只需下载一次，之后可重复使用</li>
                    <li>下载完成后将自动保存到系统缓存目录</li>
                </ul>
            </div>
            
            <div class="form-check mb-3">
                <input class="form-check-input" type="checkbox" id="download-confirmation-checkbox-${modelSize}">
                <label class="form-check-label" for="download-confirmation-checkbox-${modelSize}">
                    我已了解上述信息，确认下载模型 ${modelSize.toUpperCase()}
                </label>
            </div>
        `;
        
        // 更新模态框内容
        modalBody.innerHTML = confirmationContent;
        
        // 更新按钮
        downloadBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>确认下载';
        downloadBtn.disabled = true;
        
        // 添加复选框事件监听
        const checkbox = modal.querySelector(`#download-confirmation-checkbox-${modelSize}`);
        checkbox.addEventListener('change', () => {
            downloadBtn.disabled = !checkbox.checked;
        });
        
        // 更新按钮点击事件
        downloadBtn.onclick = () => {
            if (checkbox.checked) {
                console.log(`确认下载按钮被点击，准备开始下载模型: ${modelSize.toUpperCase()}`);
                this.addLogEntry(`确认下载按钮被点击，准备开始下载模型: ${modelSize.toUpperCase()}`, 'info');
                
                // 恢复原始内容
                modalBody.innerHTML = originalContent;
                
                // 重新获取元素引用
                const newDownloadBtn = modal.querySelector(`#download-model-btn-${modelSize}`);
                const progressContainer = modal.querySelector(`#download-progress-container-${modelSize}`);
                
                // 显示进度容器
                progressContainer.style.display = 'block';
                
                // 添加调试日志
                console.log('确认下载按钮被点击，准备开始下载模型:', modelSize);
                
                // 开始下载
                this.downloadModel(modelSize, modal);
            }
        };
    }
    
    async downloadModel(modelSize, modal) {
        const downloadBtn = modal.querySelector(`#download-model-btn-${modelSize}`);
        const progressContainer = modal.querySelector(`#download-progress-container-${modelSize}`);
        const progressBar = modal.querySelector(`#download-progress-${modelSize}`);
        const statusDiv = modal.querySelector(`#download-status-${modelSize}`);
        
        // 显示进度容器，禁用下载按钮
        progressContainer.style.display = 'block';
        downloadBtn.disabled = true;
        downloadBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>下载中...';
        
        // 设置WebSocket监听器
        const modelDownloadHandler = (data) => {
            console.log('收到模型下载进度:', data);
            this.addLogEntry(`收到模型下载进度: ${JSON.stringify(data)}`, 'info');
            
            if (data.model_size === modelSize) {
                console.log(`模型大小匹配: ${data.model_size} === ${modelSize}`);
                this.addLogEntry(`模型大小匹配: ${data.model_size} === ${modelSize}`, 'info');
                
                if (data.status === 'starting') {
                    console.log('处理starting状态');
                    statusDiv.textContent = data.message;
                    progressBar.style.width = '10%';
                    progressBar.setAttribute('aria-valuenow', '10');
                    progressBar.textContent = '10%';
                    
                    // 同时更新页面上的下载进度条
                    this.updateMainDownloadProgress(data);
                } else if (data.status === 'progress') {
                    console.log('处理progress状态');
                    const progress = data.progress || 0;
                    progressBar.style.width = `${progress}%`;
                    progressBar.setAttribute('aria-valuenow', progress);
                    progressBar.textContent = `${progress}%`;
                    statusDiv.textContent = data.message || `下载进度: ${progress}%`;
                    
                    // 同时更新页面上的下载进度条
                    this.updateMainDownloadProgress(data);
                } else if (data.status === 'completed') {
                    console.log('处理completed状态');
                    progressBar.style.width = '100%';
                    progressBar.setAttribute('aria-valuenow', '100');
                    progressBar.textContent = '100%';
                    progressBar.classList.remove('progress-bar-animated');
                    statusDiv.textContent = data.message;
                    
                    // 更新按钮状态
                    downloadBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>下载完成';
                    downloadBtn.classList.remove('btn-primary');
                    downloadBtn.classList.add('btn-success');
                    
                    // 刷新已安装模型列表
                    this.updateInstalledModelsList();
                    
                    // 2秒后关闭模态框
                    setTimeout(() => {
                        modal.modalInstance.hide();
                    }, 2000);
                } else if (data.status === 'error') {
                    console.log('处理error状态');
                    statusDiv.textContent = `错误: ${data.message}`;
                    progressBar.classList.remove('progress-bar-animated');
                    progressBar.classList.add('bg-danger');
                    
                    // 恢复按钮状态
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>重试';
                    downloadBtn.classList.remove('btn-primary');
                    downloadBtn.classList.add('btn-danger');
                } else if (data.status === 'info') {
                    console.log('处理info状态');
                    statusDiv.textContent = data.message;
                }
            } else {
                console.log(`模型大小不匹配: ${data.model_size} !== ${modelSize}`);
                this.addLogEntry(`模型大小不匹配: ${data.model_size} !== ${modelSize}`, 'warning');
            }
        };
        
        // 添加WebSocket监听器
        this.socket.on('model_download_progress', modelDownloadHandler);
        
        // 添加调试日志
        console.log('WebSocket监听器已添加，等待下载进度...');
        this.addLogEntry(`WebSocket监听器已添加，等待下载模型 ${modelSize.toUpperCase()} 的进度...`, 'info');
        console.log('当前WebSocket连接状态:', this.socket.connected ? '已连接' : '未连接');
        this.addLogEntry(`当前WebSocket连接状态: ${this.socket.connected ? '已连接' : '未连接'}`, 'info');
        
        try {
            // 添加调试日志
            console.log('发送下载请求，模型大小:', modelSize);
            this.addLogEntry(`发送下载请求，模型大小: ${modelSize.toUpperCase()}`, 'info');
            
            // 发送下载请求
            const response = await fetch('/api/download-whisper-model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ model_size: modelSize })
            });
            
            console.log('下载请求响应状态:', response.status);
            this.addLogEntry(`下载请求响应状态: ${response.status}`, 'info');
            
            const data = await response.json();
            console.log('下载请求响应数据:', data);
            this.addLogEntry(`下载请求响应数据: ${JSON.stringify(data)}`, 'info');
            
            if (response.ok) {
                if (data.already_exists) {
                    statusDiv.textContent = '模型已存在，无需下载';
                    progressBar.style.width = '100%';
                    progressBar.setAttribute('aria-valuenow', '100');
                    progressBar.textContent = '100%';
                    
                    // 更新按钮状态
                    downloadBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>已存在';
                    downloadBtn.classList.remove('btn-primary');
                    downloadBtn.classList.add('btn-success');
                    
                    // 刷新已安装模型列表
                    this.updateInstalledModelsList();
                    
                    // 1秒后关闭模态框
                    setTimeout(() => {
                        modal.modalInstance.hide();
                    }, 1000);
                } else {
                    // 下载已开始，等待WebSocket进度更新
                    progressBar.classList.add('progress-bar-animated', 'progress-bar-striped');
                    this.addLogEntry(`开始下载模型 ${modelSize.toUpperCase()}`, 'info');
                }
            } else {
                console.log('下载请求失败，响应状态:', response.status);
                this.addLogEntry(`下载请求失败，响应状态: ${response.status}`, 'error');
                throw new Error(data.error || '下载请求失败');
            }
        } catch (error) {
            console.error('下载请求错误:', error);
            this.addLogEntry(`下载请求错误: ${error.message}`, 'error');
            
            statusDiv.textContent = `错误: ${error.message}`;
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-danger');
            
            // 恢复按钮状态
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>重试';
            downloadBtn.classList.remove('btn-primary');
            downloadBtn.classList.add('btn-danger');
            
            this.addLogEntry(`模型下载失败: ${error.message}`, 'error');
        }
        
        // 模态框关闭时移除WebSocket监听器
        modal.addEventListener('hidden.bs.modal', () => {
            console.log('模态框关闭，移除WebSocket监听器');
            this.addLogEntry('模态框关闭，移除WebSocket监听器', 'info');
            this.socket.off('model_download_progress', modelDownloadHandler);
            // 从DOM中移除模态框
            modal.remove();
        });
    }
    
    /**
     * 更新页面上的主要下载进度条
     * @param {Object} data - 下载进度数据
     */
    updateMainDownloadProgress(data) {
        const downloadProgressDiv = document.getElementById('model-download-progress');
        const downloadProgressBar = document.getElementById('model-download-progress-bar');
        const downloadPercent = document.getElementById('model-download-percent');
        const downloadSize = document.getElementById('model-download-size');
        const downloadSpeed = document.getElementById('model-download-speed');
        const downloadTitle = document.getElementById('model-download-title');
        
        if (downloadProgressDiv && downloadProgressBar) {
            downloadProgressDiv.style.display = 'block';
            
            if (data.status === 'starting') {
                downloadTitle.textContent = `正在下载模型 ${data.model_size.toUpperCase()}...`;
                downloadProgressBar.style.width = '10%';
                downloadProgressBar.setAttribute('aria-valuenow', '10');
                downloadPercent.textContent = '10%';
                downloadSize.textContent = '0 MB / ' + this.getModelSizeInfo(data.model_size);
                downloadSpeed.textContent = '计算中...';
            } else if (data.status === 'progress') {
                const progress = data.progress || 0;
                downloadTitle.textContent = `正在下载模型 ${data.model_size.toUpperCase()}...`;
                downloadProgressBar.style.width = `${progress}%`;
                downloadProgressBar.setAttribute('aria-valuenow', progress);
                downloadPercent.textContent = `${progress}%`;
                
                if (data.downloaded && data.total) {
                    const downloadedMB = (data.downloaded / (1024 * 1024)).toFixed(1);
                    const totalMB = (data.total / (1024 * 1024)).toFixed(1);
                    downloadSize.textContent = `${downloadedMB} MB / ${totalMB} MB`;
                }
                
                if (data.speed) {
                    const speedKB = (data.speed / 1024).toFixed(1);
                    downloadSpeed.textContent = `${speedKB} KB/s`;
                }
            } else if (data.status === 'completed') {
                downloadTitle.textContent = `模型 ${data.model_size.toUpperCase()} 下载完成`;
                downloadProgressBar.style.width = '100%';
                downloadProgressBar.setAttribute('aria-valuenow', '100');
                downloadPercent.textContent = '100%';
                downloadSpeed.textContent = '完成';
                
                // 3秒后隐藏进度条
                setTimeout(() => {
                    downloadProgressDiv.style.display = 'none';
                }, 3000);
            } else if (data.status === 'error') {
                downloadTitle.textContent = `模型 ${data.model_size.toUpperCase()} 下载失败`;
                downloadSpeed.textContent = '错误';
                downloadProgressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                downloadProgressBar.classList.add('bg-danger');
            }
        }
    }

    updateEstimatedSize() {
        const bitrate = this.bitrate.value;
        const duration = parseFloat(this.totalDuration.textContent) || 0;

        // Estimate file size (in MB)
        const sizeMB = (parseFloat(bitrate) * duration * 60) / (8 * 1024);

        this.estimatedSize.textContent = `约 ${sizeMB.toFixed(1)} MB`;
    }

    async createVideo() {
        if (!this.validateInputs()) {
            return;
        }

        this.createVideoBtn.disabled = true;
        this.createVideoBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2"></span>
            创建中...
        `;

        // Get current page timings
        this.updateTotalDuration();

        // 获取输出文件名
        let outputName = this.outputName ? this.outputName.value : '';
        
        // 如果主输出文件名为空，尝试从自定义输出文件名获取
        if (!outputName) {
            const customOutputName = document.getElementById('output-name-custom');
            if (customOutputName) {
                outputName = customOutputName.value;
            }
        }
        
        // 设置默认输出文件名为字幕文件名或音频文件名（仅修改后缀）
        let defaultOutputName = 'video';
        if (this.uploadedFiles.subs) {
            // 优先使用字幕文件名
            const subsFileName = this.uploadedFiles.subs.name;
            const lastDotIndex = subsFileName.lastIndexOf('.');
            // 确保文件名不为空且不是以点开头
            if (lastDotIndex > 0) {
                defaultOutputName = subsFileName.substring(0, lastDotIndex);
            } else {
                defaultOutputName = subsFileName || 'video';
            }
        } else if (this.uploadedFiles.audio) {
            // 如果没有字幕文件，则使用音频文件名
            const audioFileName = this.uploadedFiles.audio.name;
            const lastDotIndex = audioFileName.lastIndexOf('.');
            // 确保文件名不为空且不是以点开头
            if (lastDotIndex > 0) {
                defaultOutputName = audioFileName.substring(0, lastDotIndex);
            } else {
                defaultOutputName = audioFileName || 'video';
            }
        }

        // 获取当前处理的书名
        const bookName = this.getCurrentBookName() || "默认书籍";
        
        const config = {
            pdf_key: this.uploadedFiles.pdf.key || this.uploadedFiles.pdf.name,
            audio_key: this.uploadedFiles.audio.key || this.uploadedFiles.audio.name,
            subs_key: this.uploadedFiles.subs.key || this.uploadedFiles.subs.name,
            output_name: outputName || defaultOutputName,
            book_name: bookName, // 添加书名参数
            start_page: parseInt(this.timingStartPage.value), // 使用翻页点设置区域的页面范围
            end_page: parseInt(this.timingEndPage.value),     // 使用翻页点设置区域的页面范围
            quality: this.quality.value,
            bitrate: this.bitrate.value,
            resolution: this.resolution.value || null,
            page_timings: this.pageTimings,
            vertical_layout: this.verticalLayout.checked, // 竖排布局选项
            odd_right_even_left: this.oddRightEvenLeft ? this.oddRightEvenLeft.checked : false, // 页面排列顺序
            transition_effect: this.transitionEffect.value, // 翻页效果选项
            // 裁剪设置
            enable_crop: this.enableCrop ? this.enableCrop.checked : false,
            crop_settings: {
                odd_pages: {
                    top: this.oddTopCrop ? parseInt(this.oddTopCrop.value) || 0 : 0,
                    bottom: this.oddBottomCrop ? parseInt(this.oddBottomCrop.value) || 0 : 0,
                    left: this.oddLeftCrop ? parseInt(this.oddLeftCrop.value) || 0 : 0,
                    right: this.oddRightCrop ? parseInt(this.oddRightCrop.value) || 0 : 0
                },
                even_pages: {
                    top: this.evenTopCrop ? parseInt(this.evenTopCrop.value) || 0 : 0,
                    bottom: this.evenBottomCrop ? parseInt(this.evenBottomCrop.value) || 0 : 0,
                    left: this.evenLeftCrop ? parseInt(this.evenLeftCrop.value) || 0 : 0,
                    right: this.evenRightCrop ? parseInt(this.evenRightCrop.value) || 0 : 0
                }
            }
        };

        // 保存翻页点数据到本地存储，以便后续调用
        this.savePageTimingsData();

        try {
            const response = await fetch('/api/create-video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            const data = await response.json();

            if (response.ok) {
                this.currentJob = data.job_id;
                this.showProgress(data.job_id);
                this.startProgressPolling(data.job_id);
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            this.showError(`视频创建失败: ${error.message}`);
            this.resetCreateButton();
        }
    }

    validateInputs() {
        if (!this.uploadedFiles.pdf || !this.uploadedFiles.audio || !this.uploadedFiles.subs) {
            this.showError('请先上传所有必需的文件');
            return false;
        }

        // Check if page range is empty (使用翻页点设置区域的页面范围)
        if (!this.timingStartPage.value || !this.timingEndPage.value) {
            this.showError('请先设置PDF页面范围');
            return false;
        }

        const startPage = parseInt(this.timingStartPage.value);
        const endPage = parseInt(this.timingEndPage.value);

        if (isNaN(startPage) || isNaN(endPage) || startPage < 1 || startPage > this.pageCount) {
            this.showError(`起始页码必须在 1 到 ${this.pageCount} 之间`);
            return false;
        }

        if (endPage < startPage || endPage > this.pageCount) {
            this.showError(`结束页码必须在 ${startPage} 到 ${this.pageCount} 之间`);
            return false;
        }

        return true;
    }

    showProgress(jobId) {
        this.progressSection.style.display = 'block';
        this.createSection.style.display = 'none';
        this.jobId.textContent = jobId;
        this.startTime.textContent = new Date().toLocaleTimeString();
        
        // 显示日志区域
        if (this.logSection) {
            this.logSection.style.display = 'block';
        }
        
        // 添加开始日志
        this.addLogEntry(`开始处理任务: ${jobId}`);
    }

    startProgressPolling(jobId) {
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/job-status/${jobId}`);
                const data = await response.json();

                if (response.ok) {
                    this.updateProgress(data);

                    if (data.status === 'completed') {
                        clearInterval(pollInterval);
                        this.showResults(data);
                    } else if (data.status === 'failed') {
                        clearInterval(pollInterval);
                        // 确保日志区域可见
                        if (this.logSection) {
                            this.logSection.style.display = 'block';
                        }
                        this.addLogEntry(`视频创建失败: ${data.message}`);
                        this.showError(`视频创建失败: ${data.message}`);
                        this.resetCreateButton();
                    }
                } else {
                    throw new Error(data.error);
                }
            } catch (error) {
                console.error('Progress polling error:', error);
                clearInterval(pollInterval);
                // 确保日志区域可见
                if (this.logSection) {
                    this.logSection.style.display = 'block';
                }
                this.addLogEntry(`状态检查失败: ${error.message}`);
                this.showError(`状态检查失败: ${error.message}`);
                this.resetCreateButton();
            }
        }, 2000);
    }

    updateProgress(data) {
        this.progressBar.style.width = `${data.progress}%`;
        this.progressPercent.textContent = `${data.progress}%`;
        this.progressMessage.textContent = data.message;
        
        // 只在进度达到特定节点时添加日志信息，减少日志频率
        if (data.message && this.logContainer && data.progress % 10 === 0) {
            this.addLogEntry(`进度: ${data.progress}% - ${data.message}`);
        }
    }

    showResults(data) {
        this.progressSection.style.display = 'none';
        this.resultsSection.style.display = 'block';
        
        // 确保日志区域保持可见
        if (this.logSection) {
            this.logSection.style.display = 'block';
        }

        // 设置成功提示信息
        const resultsMessage = document.getElementById('results-message');
        const resultsAlert = document.getElementById('results-alert');
        if (resultsMessage && resultsAlert) {
            resultsMessage.textContent = '视频创建成功！';
            // 确保使用success样式
            resultsAlert.className = 'alert alert-success';
            const icon = resultsAlert.querySelector('i');
            if (icon) {
                icon.className = 'bi me-2';
            }
        }

        if (data.output_filename) {
            this.resultFilename.textContent = data.output_filename;
            
            // 获取书名，如果没有则使用默认值
            const bookName = data.book_name;
            
            // 设置下载链接
            this.downloadLink.href = `/download/${bookName}/${data.output_filename}`;
            
            // 显示"打开本地目录"按钮
            const openDirectoryBtn = document.getElementById('open-directory-btn');
            if (openDirectoryBtn) {
                openDirectoryBtn.style.display = 'inline-block';
                openDirectoryBtn.setAttribute('data-book-name', bookName);
            }
            
            // 显示"预览视频"按钮
            if (this.previewVideoBtn) {
                this.previewVideoBtn.style.display = 'inline-block';
                this.previewVideoBtn.setAttribute('data-book-name', bookName);
                this.previewVideoBtn.setAttribute('data-video-filename', data.output_filename);
            }
            
            // 设置创建时间
            this.resultTime.textContent = new Date().toLocaleString();
            
            // 获取视频元数据并显示完整信息
            this.getVideoMetadataAndUpdateDisplay(bookName, data.output_filename);
            
            // 添加成功日志
            this.addLogEntry(`视频创建成功: ${data.output_filename}`);
            
            // 在已上传文件列表中显示视频文件信息
            this.getVideoMetadataAndDisplay(bookName, data.output_filename);
            
            // 自动显示视频预览
            setTimeout(() => {
                this.showVideoPreview(bookName, data.output_filename);
            }, 1000);
        }

        this.resetCreateButton();
        // this.loadJobsHistory(); // 已移除处理历史功能
    }
    
    // 获取视频元数据并更新主结果区域显示
    async getVideoMetadataAndUpdateDisplay(bookName, videoFilename) {
        try {
            // 获取视频文件信息
            const response = await fetch(`/api/check-video-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(videoFilename)}`);
            const data = await response.json();
            
            if (response.ok && data.exists) {
                // 更新主结果区域的视频文件信息
                this.updateMainResultVideoInfo(videoFilename, data);
            }
        } catch (error) {
            console.error('获取视频元数据失败:', error);
            // 如果获取失败，至少显示文件大小
            this.resultFilesize.textContent = '获取文件大小失败';
        }
    }
    
    // 更新主结果区域的视频文件信息
    updateMainResultVideoInfo(videoFilename, videoData) {
        // 构建视频文件信息字符串
        let infoText = `文件大小：${videoData.filesize || '未知大小'} | 创建时间：${this.resultTime.textContent}`;
        
        // 添加视频元数据信息
        if (videoData.metadata) {
            const metadata = videoData.metadata;
            if (metadata.resolution) {
                infoText += ` | 分辨率：${metadata.resolution}`;
            }
            if (metadata.duration) {
                infoText += ` | 时长：${metadata.duration}`;
            }
            if (metadata.codec) {
                infoText += ` | 编码：${metadata.codec}`;
            }
            if (metadata.bitrate) {
                infoText += ` | 比特率：${metadata.bitrate}`;
            }
            if (metadata.fps) {
                infoText += ` | 帧率：${metadata.fps}`;
            }
        }
        
        // 更新文件大小显示为完整信息
        this.resultFilesize.textContent = infoText;
    }

    // 获取视频元数据并在已上传文件列表中显示
    async getVideoMetadataAndDisplay(bookName, videoFilename) {
        try {
            // 获取视频文件信息
            const response = await fetch(`/api/check-video-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(videoFilename)}`);
            const data = await response.json();
            
            if (response.ok && data.exists) {
                // 在已上传文件列表中显示视频文件信息
                this.displayVideoFileInUploadedList(videoFilename, data);
            }
        } catch (error) {
            console.error('获取视频元数据失败:', error);
        }
    }

    async getFileSize(filename) {
        try {
            // 获取书名，如果没有则使用默认值
            const bookName = this.getCurrentBookName();
            
            // 使用check-video-exists API获取文件大小
            const response = await fetch(`/api/check-video-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(filename)}`);
            const data = await response.json();
            
            if (response.ok && data.exists) {
                // 使用API返回的文件大小
                this.resultFilesize.textContent = data.filesize;
            } else {
                this.resultFilesize.textContent = '文件大小未知';
            }
        } catch (error) {
            console.error('获取文件大小失败:', error);
            this.resultFilesize.textContent = '获取文件大小失败';
        }
    }

    resetCreateButton() {
        this.createVideoBtn.disabled = false;
        this.createVideoBtn.innerHTML = `
            <i class="bi bi-play-circle me-2"></i>
            开始创建视频
        `;
    }

    // 添加日志条目
    addLogEntry(message, level = 'info') {
        // 检查是否禁用了界面日志显示
        if (this.disableUILogging) {
            return;
        }
        
        // 获取日志内容容器，如果不存在则使用日志容器
        const logContent = document.getElementById('log-content') || this.logContainer;
        if (!logContent) return;
        
        // 如果已经有待处理的日志，添加到队列中
        if (!this.pendingLogEntries) {
            this.pendingLogEntries = [];
        }
        
        this.pendingLogEntries.push({ message, level });
        
        // 使用防抖技术，延迟处理日志更新
        if (this.logUpdateTimeout) {
            clearTimeout(this.logUpdateTimeout);
        }
        
        this.logUpdateTimeout = setTimeout(() => {
            this.processPendingLogEntries();
        }, 50); // 减少延迟到50ms，提高实时性
    }
    
    // 处理待处理的日志条目
    processPendingLogEntries() {
        if (!this.pendingLogEntries || this.pendingLogEntries.length === 0) return;
        
        // 获取日志内容容器，如果不存在则使用日志容器
        const logContent = document.getElementById('log-content') || this.logContainer;
        if (!logContent) return;
        
        // 创建文档片段，减少DOM操作
        const fragment = document.createDocumentFragment();
        
        // 批量添加所有待处理的日志条目
        this.pendingLogEntries.forEach(logItem => {
            const { message, level } = logItem;
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            
            // 特殊处理字幕内容，使其更加突出
            if (message && message.startsWith('字幕:')) {
                logEntry.className = `log-entry log-${level} subtitle-entry`;
                logEntry.innerHTML = `<span class="log-time">[${timestamp}]</span> <span class="log-message subtitle-message">${message}</span>`;
            } else {
                logEntry.className = `log-entry log-${level}`;
                logEntry.innerHTML = `<span class="log-time">[${timestamp}]</span> <span class="log-message">${message}</span>`;
            }
            
            fragment.appendChild(logEntry);
        });
        
        // 一次性添加所有日志条目
        logContent.appendChild(fragment);
        
        // 自动滚动到底部
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
        
        // 限制日志条目数量，避免内存占用过多
        const maxLogEntries = 200; // 增加最大日志条目数量
        while (logContent.children.length > maxLogEntries) {
            logContent.removeChild(logContent.firstChild);
        }
        
        // 清空待处理的日志条目
        this.pendingLogEntries = [];
        this.logUpdateTimeout = null;
    }

    // 清除日志
    clearLog() {
        // 获取日志内容容器，如果不存在则使用日志容器
        const logContent = document.getElementById('log-content') || this.logContainer;
        if (!logContent) return;
        
        logContent.innerHTML = '';
        this.addLogEntry('日志已清除');
    }

    // 切换日志显示/隐藏
    toggleLog() {
        if (!this.logContainer || !this.toggleLogBtn) return;
        
        this.logExpanded = !this.logExpanded;
        
        if (this.logExpanded) {
            this.logContainer.style.maxHeight = 'none';
            this.toggleLogBtn.innerHTML = '<i class="bi bi-chevron-up"></i> 收起';
        } else {
            this.logContainer.style.maxHeight = '300px';
            this.toggleLogBtn.innerHTML = '<i class="bi bi-chevron-down"></i> 展开';
        }
    }
    
    // 切换界面日志显示
    toggleUILogging() {
        this.disableUILogging = !this.disableUILogging;
        if (this.disableUILogging) {
            console.log('界面日志已禁用');
            // 添加一个控制台日志，而不是界面日志
        } else {
            console.log('界面日志已启用');
            this.addLogEntry('界面日志已启用');
        }
    }

    async savePageTimingsData() {
        // 保存翻页点数据到服务器文件
        try {
            // 获取当前处理的书名
            const bookName = this.getCurrentBookName();
            console.log('尝试保存配置，书名:', bookName);
            
            // 获取当前的翻页点数据
            const pageTimingInputs = document.querySelectorAll('.page-timing');
            const pageTimings = [];
            const errors = [];
            
            // 验证并转换每个翻页时间值
            for (let i = 0; i < pageTimingInputs.length; i++) {
                const input = pageTimingInputs[i];
                const value = input.value.trim();
                
                // 检查是否为空
                if (!value) {
                    errors.push(`第 ${i + 1} 个翻页时间不能为空`);
                    continue;
                }
                
                let timeValue = 0;
                
                // 如果是SRT时间格式，转换为秒
                if (value.includes(':') && value.includes(',')) {
                    const parts = value.split(':');
                    if (parts.length !== 3) {
                        errors.push(`第 ${i + 1} 个翻页时间格式错误: ${value}`);
                        continue;
                    }
                    const minutes = parseInt(parts[0]);
                    const seconds = parseInt(parts[1]);
                    const milliseconds = parseInt(parts[2].split(',')[1]);
                    
                    if (isNaN(minutes) || isNaN(seconds) || isNaN(milliseconds)) {
                        errors.push(`第 ${i + 1} 个翻页时间包含非数字: ${value}`);
                        continue;
                    }
                    
                    timeValue = minutes * 60 + seconds + milliseconds / 1000;
                }
                // 如果是带小数点的秒数格式
                else if (value.includes('.')) {
                    timeValue = parseFloat(value);
                    if (isNaN(timeValue)) {
                        errors.push(`第 ${i + 1} 个翻页时间不是有效数字: ${value}`);
                        continue;
                    }
                }
                // 如果是整数秒数格式
                else {
                    timeValue = parseInt(value);
                    if (isNaN(timeValue)) {
                        errors.push(`第 ${i + 1} 个翻页时间不是有效数字: ${value}`);
                        continue;
                    }
                }
                
                // 检查是否为负数
                if (timeValue < 0) {
                    errors.push(`第 ${i + 1} 个翻页时间不能为负数: ${value}`);
                    continue;
                }
                
                // 检查是否大于前一个值
                if (pageTimings.length > 0 && timeValue <= pageTimings[pageTimings.length - 1]) {
                    errors.push(`第 ${i + 1} 个翻页时间 (${timeValue.toFixed(2)}秒) 必须大于前一个时间 (${pageTimings[pageTimings.length - 1].toFixed(2)}秒)`);
                    continue;
                }
                
                pageTimings.push(timeValue);
            }
            
            // 如果有错误，显示错误信息并停止保存
            if (errors.length > 0) {
                const errorMessage = '配置验证失败：\n\n' + errors.join('\n');
                console.error('配置验证失败:', errors);
                this.showError(errorMessage);
                return false;
            }
            
            // 检查是否有翻页时间数据
            if (pageTimings.length === 0) {
                this.showError('没有有效的翻页时间数据');
                return false;
            }
            
            // 获取页面范围
            const startPage = this.timingStartPage.value;
            const endPage = this.timingEndPage.value;
            
            // 获取竖排布局选项
            const verticalLayout = this.verticalLayout.checked;
            
            // 获取页面排列顺序设置
            const oddRightEvenLeft = this.oddRightEvenLeft ? this.oddRightEvenLeft.checked : false;
            
            // 获取PDF边界裁剪设置
            const enableCrop = this.enableCrop ? this.enableCrop.checked : false;
            const cropSettings = {
                odd: {
                    top: this.oddTopCrop ? parseInt(this.oddTopCrop.value) || 0 : 0,
                    bottom: this.oddBottomCrop ? parseInt(this.oddBottomCrop.value) || 0 : 0,
                    left: this.oddLeftCrop ? parseInt(this.oddLeftCrop.value) || 0 : 0,
                    right: this.oddRightCrop ? parseInt(this.oddRightCrop.value) || 0 : 0
                },
                even: {
                    top: this.evenTopCrop ? parseInt(this.evenTopCrop.value) || 0 : 0,
                    bottom: this.evenBottomCrop ? parseInt(this.evenBottomCrop.value) || 0 : 0,
                    left: this.evenLeftCrop ? parseInt(this.evenLeftCrop.value) || 0 : 0,
                    right: this.evenRightCrop ? parseInt(this.evenRightCrop.value) || 0 : 0
                }
            };
            
            // 准备要保存的数据
            const configData = {
                pageTimings: pageTimings,
                startPage: startPage,
                endPage: endPage,
                verticalLayout: verticalLayout,
                oddRightEvenLeft: oddRightEvenLeft,
                enableCrop: enableCrop,
                cropSettings: cropSettings,
                timestamp: new Date().toISOString()
            };
            
            console.log('准备保存的配置数据:', configData);
            
            // 获取字幕文件名（如果有的话）
            // 优先使用音频文件名作为配置基准
            let configBaseName = this.uploadedFiles.audio?.name || 
                              this.uploadedFiles.subs?.name || 
                              '默认配置';
            
            // 移除文件扩展名
            configBaseName = configBaseName.replace(/\.[^/.]+$/, '');
            
            // 添加必要字段到配置数据
            configData.audioFilename = this.uploadedFiles.audio?.name || '';
            // 从文件名提取章节名称（移除序号和扩展名）
            let chapterName = configBaseName
              .replace(/^第[零一二三四五六七八九十百千]+回/, '') // 移除开头的『第X回』
              .replace(/[【】]/g, '') // 移除中括号
              .replace(/[-_()（）、，。]/g, ' ') // 替换特殊字符为空格
              .trim();
            
            // 如果章节名称为空或者是文件扩展名（如m4a、mp3等），则使用默认值
            if (!chapterName || ['m4a', 'mp3', 'wav', 'srt', 'pdf'].includes(chapterName.toLowerCase())) {
                chapterName = '默认章节';
            }
            
            configData.chapterName = chapterName;
            configData.subtitleFilename = configBaseName + '.srt';
            
            // 发送保存请求
            const response = await fetch('/api/save-config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    book_name: bookName,
                    subtitle_filename: configBaseName + '.srt',
                    audio_filename: this.uploadedFiles.audio?.name || '',
                    config_data: configData
                })
            });
            
            const result = await response.json();
            console.log('保存配置的响应:', response.status, result);
            
            if (response.ok) {
                console.log('翻页点数据已保存到服务器文件');
                return true;
            } else {
                console.error('保存翻页点数据失败:', result.error);
                return false;
            }
        } catch (error) {
            console.error('保存翻页点数据失败:', error);
            return false;
        }
    }

    // 加载配置数据到表单
    loadConfigData(configData, showUserMessage = true) {
        try {
            console.log('loadConfigData方法被调用，配置数据:', configData);
            
            // 恢复页面范围
            if (configData.startPage) {
                this.timingStartPage.value = configData.startPage;
                console.log('设置起始页:', configData.startPage);
            }
            if (configData.endPage) {
                this.timingEndPage.value = configData.endPage;
                console.log('设置结束页:', configData.endPage);
            }
            
            // 恢复竖排布局选项
            if (configData.verticalLayout !== undefined) {
                this.verticalLayout.checked = configData.verticalLayout;
                console.log('设置竖排布局:', configData.verticalLayout);
                
                // 根据竖排布局选项显示或隐藏页面排列顺序设置
                if (this.pageOrderSettings) {
                    this.pageOrderSettings.style.display = configData.verticalLayout ? 'block' : 'none';
                }
            }
            
            // 恢复页面排列顺序设置
            if (configData.oddRightEvenLeft !== undefined && this.oddRightEvenLeft) {
                this.oddRightEvenLeft.checked = configData.oddRightEvenLeft;
                console.log('设置页面排列顺序:', configData.oddRightEvenLeft);
            }
            
            // 恢复PDF边界裁剪设置
            if (configData.enableCrop !== undefined && this.enableCrop) {
                this.enableCrop.checked = configData.enableCrop;
                this.cropSettings.style.display = configData.enableCrop ? 'block' : 'none';
                console.log('设置启用裁剪:', configData.enableCrop);
            }
            
            if (configData.cropSettings) {
                // 恢复奇数页裁剪设置
                if (configData.cropSettings.odd) {
                    if (this.oddTopCrop) this.oddTopCrop.value = configData.cropSettings.odd.top || 0;
                    if (this.oddBottomCrop) this.oddBottomCrop.value = configData.cropSettings.odd.bottom || 0;
                    if (this.oddLeftCrop) this.oddLeftCrop.value = configData.cropSettings.odd.left || 0;
                    if (this.oddRightCrop) this.oddRightCrop.value = configData.cropSettings.odd.right || 0;
                }
                
                // 恢复偶数页裁剪设置
                if (configData.cropSettings.even) {
                    if (this.evenTopCrop) this.evenTopCrop.value = configData.cropSettings.even.top || 0;
                    if (this.evenBottomCrop) this.evenBottomCrop.value = configData.cropSettings.even.bottom || 0;
                    if (this.evenLeftCrop) this.evenLeftCrop.value = configData.cropSettings.even.left || 0;
                    if (this.evenRightCrop) this.evenRightCrop.value = configData.cropSettings.even.right || 0;
                }
                console.log('设置裁剪参数:', configData.cropSettings);
            }
            
            // 恢复翻页点数据
            if (configData.pageTimings && Array.isArray(configData.pageTimings)) {
                this.pageTimings = [...configData.pageTimings];
                console.log('已恢复翻页点数据:', this.pageTimings);
            }
            
            console.log('页面范围设置后:', this.timingStartPage.value, '到', this.timingEndPage.value);
            console.log('竖排布局设置后:', this.verticalLayout.checked);
            console.log('翻页点数据恢复后:', this.pageTimings);
            
            // 强制重新生成翻页点输入框
            console.log('重新生成翻页点输入框...');
            
            // 确保翻页时间设置部分是显示状态
            if (this.pageTimingSection) {
                this.pageTimingSection.style.display = 'block';
                console.log('设置翻页时间设置部分为显示状态');
            }
            
            this.generatePageTimingInputs();
            
            // 更新总时长
            console.log('更新总时长...');
            this.updateTotalDuration();
            
            // 使用setTimeout确保页面范围设置后再次生成输入框
            setTimeout(() => {
                console.log('延迟重新生成翻页点输入框...');
                
                // 确保翻页时间设置部分是显示状态
                if (this.pageTimingSection) {
                    this.pageTimingSection.style.display = 'block';
                }
                
                this.generatePageTimingInputs();
                this.updateTotalDuration();
            }, 100);
            
            console.log('已加载配置数据到表单');
            
            // 显示配置已加载消息
            if (showUserMessage) {
                this.showSuccess('配置已自动加载');
            }
        } catch (error) {
            console.error('加载配置数据到表单失败:', error);
            this.addLogEntry(`加载配置数据到表单失败: ${error.message}`);
        }
    }

    // 轮询检查配置文件是否可用
    async pollForConfigAvailability(bookName, attemptCount, maxAttempts) {
        console.log(`轮询检查配置文件可用性 (尝试 ${attemptCount + 1}/${maxAttempts})`);
        
        try {
            // 构建API URL
            let apiUrl = `/api/load-config/${encodeURIComponent(bookName)}`;
            
            // 添加查询参数
            if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
                apiUrl += `?subtitle_filename=${encodeURIComponent(this.uploadedFiles.subs.name)}`;
            } else if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                apiUrl += `?audio_filename=${encodeURIComponent(this.uploadedFiles.audio.name)}`;
            }
            
            // 尝试加载配置
            const response = await fetch(apiUrl);
            const result = await response.json();
            
            if (response.ok && result.status === 'success' && result.config_data) {
                console.log('配置文件可用，开始加载');
                
                // 确保翻页时间设置部分是显示状态
                if (this.pageTimingSection) {
                    this.pageTimingSection.style.display = 'block';
                }
                
                // 直接调用手动加载的功能代码
                const success = await this.loadPageTimingsData(true); // 显示成功提示
                
                if (success) {
                    this.showSuccess('配置已自动加载');
                    
                    // 额外检查：确保页面范围已设置
                    if (!this.timingStartPage.value || !this.timingEndPage.value) {
                        console.error('配置加载成功但页面范围为空');
                    } else {
                        console.log('配置加载成功，页面范围已设置:', this.timingStartPage.value, '到', this.timingEndPage.value);
                    }
                }
            } else if (attemptCount < maxAttempts - 1) {
                // 配置文件还不可用，等待后重试
                console.log(`配置文件还不可用，${2000}毫秒后重试`);
                
                setTimeout(() => {
                    this.pollForConfigAvailability(bookName, attemptCount + 1, maxAttempts);
                }, 2000);
            } else {
                // 达到最大尝试次数
                console.log('达到最大尝试次数，停止轮询');
                this.showError('配置文件加载超时，请手动点击"加载配置"按钮');
            }
        } catch (error) {
            console.error('轮询检查配置文件时出错:', error);
            
            if (attemptCount < maxAttempts - 1) {
                // 出错但还可以重试
                setTimeout(() => {
                    this.pollForConfigAvailability(bookName, attemptCount + 1, maxAttempts);
                }, 2000);
            } else {
                // 达到最大尝试次数
                this.showError('配置文件加载超时，请手动点击"加载配置"按钮');
            }
        }
    }

    async loadPageTimingsData(showSuccessMessage = true) {
        // 从服务器文件加载翻页点数据
        try {
            console.log('=== loadPageTimingsData方法被调用 ===');
            console.log('showSuccessMessage:', showSuccessMessage);
            
            // 获取当前处理的书名
            const bookName = this.getCurrentBookName();
            console.log('尝试加载配置，书名:', bookName);
            console.log('当前uploadedFiles:', this.uploadedFiles);
            
            // 构建API URL并添加查询参数
            let apiUrl = `/api/load-config/${encodeURIComponent(bookName)}`;
            
            // 添加字幕文件名或音频文件名作为查询参数
            if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
                apiUrl += `?subtitle_filename=${encodeURIComponent(this.uploadedFiles.subs.name)}`;
            } else if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                apiUrl += `?audio_filename=${encodeURIComponent(this.uploadedFiles.audio.name)}`;
            }
            
            console.log('API URL:', apiUrl);
            
            // 尝试使用当前书名加载配置
            let response = await fetch(apiUrl);
            let result = await response.json();
            console.log('API响应:', response.status, result);
            
            if (response.ok && result.status === 'success' && result.config_data) {
                const timingsData = result.config_data;
                console.log('加载的配置数据:', timingsData);
                
                // 确保pageTimingSection可见
                if (this.pageTimingSection) {
                    this.pageTimingSection.style.display = 'block';
                    console.log('loadPageTimingsData: 设置pageTimingSection为可见');
                } else {
                    console.error('loadPageTimingsData: pageTimingSection元素未找到');
                }
                
                // 恢复页面范围
                if (timingsData.startPage) {
                    this.timingStartPage.value = timingsData.startPage;
                    console.log('设置起始页:', timingsData.startPage);
                }
                if (timingsData.endPage) {
                    this.timingEndPage.value = timingsData.endPage;
                    console.log('设置结束页:', timingsData.endPage);
                }
                
                // 恢复竖排布局选项
                if (timingsData.verticalLayout !== undefined) {
                    this.verticalLayout.checked = timingsData.verticalLayout;
                    console.log('设置竖排布局:', timingsData.verticalLayout);
                    
                    // 根据竖排布局选项显示或隐藏页面排列顺序设置
                    if (this.pageOrderSettings) {
                        this.pageOrderSettings.style.display = timingsData.verticalLayout ? 'block' : 'none';
                    }
                }
                
                // 恢复页面排列顺序设置
                if (timingsData.oddRightEvenLeft !== undefined && this.oddRightEvenLeft) {
                    this.oddRightEvenLeft.checked = timingsData.oddRightEvenLeft;
                    console.log('设置页面排列顺序:', timingsData.oddRightEvenLeft);
                }
                
                // 恢复PDF边界裁剪设置
                if (timingsData.enableCrop !== undefined && this.enableCrop) {
                    this.enableCrop.checked = timingsData.enableCrop;
                    this.cropSettings.style.display = timingsData.enableCrop ? 'block' : 'none';
                    console.log('设置启用裁剪:', timingsData.enableCrop);
                }
                
                if (timingsData.cropSettings) {
                    // 恢复奇数页裁剪设置
                    if (timingsData.cropSettings.odd) {
                        if (this.oddTopCrop) this.oddTopCrop.value = timingsData.cropSettings.odd.top || 0;
                        if (this.oddBottomCrop) this.oddBottomCrop.value = timingsData.cropSettings.odd.bottom || 0;
                        if (this.oddLeftCrop) this.oddLeftCrop.value = timingsData.cropSettings.odd.left || 0;
                        if (this.oddRightCrop) this.oddRightCrop.value = timingsData.cropSettings.odd.right || 0;
                    }
                    
                    // 恢复偶数页裁剪设置
                    if (timingsData.cropSettings.even) {
                        if (this.evenTopCrop) this.evenTopCrop.value = timingsData.cropSettings.even.top || 0;
                        if (this.evenBottomCrop) this.evenBottomCrop.value = timingsData.cropSettings.even.bottom || 0;
                        if (this.evenLeftCrop) this.evenLeftCrop.value = timingsData.cropSettings.even.left || 0;
                        if (this.evenRightCrop) this.evenRightCrop.value = timingsData.cropSettings.even.right || 0;
                    }
                    console.log('设置裁剪参数:', timingsData.cropSettings);
                }
                
                // 恢复翻页点数据
                if (timingsData.pageTimings && Array.isArray(timingsData.pageTimings)) {
                    this.pageTimings = [...timingsData.pageTimings];
                    console.log('已恢复翻页点数据:', this.pageTimings);
                }
                
                console.log('页面范围设置后:', this.timingStartPage.value, '到', this.timingEndPage.value);
                console.log('竖排布局设置后:', this.verticalLayout.checked);
                console.log('翻页点数据恢复后:', this.pageTimings);
                
                // 确保页面范围已设置
                if (!this.timingStartPage.value || !this.timingEndPage.value) {
                    console.error('页面范围未正确设置');
                    this.addLogEntry('错误：页面范围未正确设置');
                    return false;
                }
                
                // 强制重新生成翻页点输入框
                console.log('重新生成翻页点输入框...');
                this.generatePageTimingInputs();
                
                // 更新总时长
                console.log('更新总时长...');
                this.updateTotalDuration();
                
                // 使用setTimeout确保页面范围设置后再次生成输入框
                setTimeout(() => {
                    console.log('延迟重新生成翻页点输入框...');
                    console.log('延迟时页面范围:', this.timingStartPage.value, '到', this.timingEndPage.value);
                    this.generatePageTimingInputs();
                    this.updateTotalDuration();
                    
                    // 延迟检查pageTimingSection显示状态
                    setTimeout(() => {
                        if (this.pageTimingSection) {
                            console.log('延迟检查: pageTimingSection当前显示状态:', window.getComputedStyle(this.pageTimingSection).display);
                            if (window.getComputedStyle(this.pageTimingSection).display === 'none') {
                                console.log('延迟检查: pageTimingSection被隐藏，重新设置为可见');
                                this.pageTimingSection.style.display = 'block';
                                this.addLogEntry('延迟检查: 重新设置翻页时间设置部分为显示状态');
                            }
                        } else {
                            console.error('延迟检查: pageTimingSection元素未找到');
                        }
                    }, 100);
                }, 100);
                
                console.log('已从服务器文件加载翻页点数据');
                // 显示配置已加载消息，包含文件名（如果有的话）
                if (result.config_filename && showSuccessMessage) {
                    this.showSuccess(`『${timingsData.chapterName || '配置'}』加载成功`);
                    console.log('完整配置数据:', timingsData);
                } else if (showSuccessMessage) {
                    this.showSuccess('配置已加载');
                }
                return true;
            } else if (response.ok && result.status === 'no_config') {
                console.log('配置文件不存在:', result.message);
                // 不显示错误消息，因为缺少配置文件是正常情况
                return false;
            } else if (response.status === 404) {
                console.log('未找到配置文件');
                // 不再显示错误消息，因为缺少配置文件是正常情况
                // this.showError('未找到配置文件');
                return false;
            } else {
                console.error('加载翻页点数据失败:', result.error || result.message);
                this.showError(`配置加载失败: ${result.error || result.message}`);
                return false;
            }
        } catch (error) {
            console.error('加载翻页点数据失败:', error);
            this.showError(`配置加载失败: ${error.message}`);
            return false;
        }
    }

    getCurrentBookName() {
        // 获取当前处理的书名
        // 从上传的文件名中提取书名，并进行智能处理
        try {
            console.log('getCurrentBookName方法被调用');
            console.log('uploadedFiles对象内容:', this.uploadedFiles);
            
            // 尝试从PDF文件名中提取书名
            if (this.uploadedFiles.pdf && this.uploadedFiles.pdf.name) {
                const pdfName = this.uploadedFiles.pdf.name;
                // 移除文件扩展名
                let bookName = pdfName.replace(/\.[^/.]+$/, "");
                console.log('从PDF文件名提取原始书名:', bookName);
                
                // 智能处理书名
                // 1. 检查是否包含"红楼梦"关键词
                if (bookName.includes('红楼梦')) {
                    bookName = '红楼梦';
                    console.log('检测到红楼梦关键词，使用书名:', bookName);
                    return bookName;
                }
                
                // 2. 检查是否包含"脂硯齋重評石頭記"关键词
                if (bookName.includes('脂硯齋重評石頭記')) {
                    bookName = '红楼梦';
                    console.log('检测到脂硯齋重評石頭記关键词，使用书名:', bookName);
                    return bookName;
                }
                
                // 3. 去掉括号及括号后的内容
                bookName = bookName.split('(')[0].trim();
                console.log('处理后书名:', bookName);
                return bookName;
            }
            
            // 如果没有PDF文件，尝试从其他文件中提取
            if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                const audioName = this.uploadedFiles.audio.name;
                // 移除文件扩展名
                let bookName = audioName.replace(/\.[^/.]+$/, "");
                console.log('从音频文件名提取原始书名:', bookName);
                
                // 智能处理书名
                // 1. 检查是否包含"红楼梦"关键词
                if (bookName.includes('红楼梦')) {
                    bookName = '红楼梦';
                    console.log('检测到红楼梦关键词，使用书名:', bookName);
                    return bookName;
                }
                
                // 2. 检查是否包含"脂硯齋重評石頭記"关键词
                if (bookName.includes('脂硯齋重評石頭記')) {
                    bookName = '红楼梦';
                    console.log('检测到脂硯齋重評石頭記关键词，使用书名:', bookName);
                    return bookName;
                }
                
                // 3. 去掉括号及括号后的内容
                bookName = bookName.split('(')[0].trim();
                console.log('处理后书名:', bookName);
                return bookName;
            }
            
            // 如果都没有，返回空字符串
            console.log('无法从上传文件中提取书名');
            return '';
        } catch (error) {
            console.error('获取书名失败:', error);
            return '';
        }
    }

    // 新增方法：检查已存在的上传文件
    async checkExistingUploads() {
        try {
            // 这里可以添加逻辑来检查服务器上已有的上传文件
            // 暂时留空，因为我们主要关注的是修复配置加载问题
            console.log('检查已存在的上传文件');
        } catch (error) {
            console.error('检查已存在的上传文件失败:', error);
        }
    }

    // loadJobsHistory函数已移除 - 处理历史功能已取消

    // refreshBookList函数已移除 - 处理历史功能已取消

    // renderJobsList函数已移除 - 处理历史功能已取消

    showError(message) {
        // Create toast notification
        const toastHtml = `
            <div class="toast align-items-center text-white bg-danger border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }

        const toastElement = document.createElement('div');
        toastElement.innerHTML = toastHtml;
        toastContainer.appendChild(toastElement);

        const toast = new bootstrap.Toast(toastElement.querySelector('.toast'));
        toast.show();

        // Remove after hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    showSuccess(message) {
        // Create toast notification
        const toastHtml = `
            <div class="toast align-items-center text-white bg-success border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }

        const toastElement = document.createElement('div');
        toastElement.innerHTML = toastHtml;
        toastContainer.appendChild(toastElement);

        const toast = new bootstrap.Toast(toastElement.querySelector('.toast'));
        toast.show();

        // Remove after hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    }

    // 初始化PDF预览canvas
    initializePdfCanvas() {
        console.log('初始化PDF预览canvas');
        if (!this.pdfPreviewCanvas) {
            console.error('PDF预览canvas元素不存在');
            return;
        }
        
        // 初始化渲染状态标志
        this.isRendering = false;
        
        // 设置canvas的初始尺寸和背景
        const context = this.pdfPreviewCanvas.getContext('2d');
        this.pdfPreviewCanvas.width = 800;
        this.pdfPreviewCanvas.height = 600;
        
        // 清除画布并添加白色背景
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, this.pdfPreviewCanvas.width, this.pdfPreviewCanvas.height);
        
        // 显示加载提示
        context.fillStyle = '#666';
        context.font = '16px Arial';
        context.textAlign = 'center';
        context.fillText('正在准备PDF预览...', this.pdfPreviewCanvas.width / 2, this.pdfPreviewCanvas.height / 2);
        
        console.log('PDF预览canvas初始化完成');
    }
    
    // 清理PDF资源
    cleanupPdfResources() {
        console.log('清理PDF资源');
        
        // 取消正在进行的渲染任务
        if (this.currentRenderTask) {
            try {
                this.currentRenderTask.cancel();
            } catch (e) {
                console.log('取消渲染任务失败:', e);
            }
            this.currentRenderTask = null;
        }
        
        // 清理PDF文档
        if (this.pdfDoc) {
            try {
                // 尝试销毁PDF文档对象
                if (typeof this.pdfDoc.destroy === 'function') {
                    this.pdfDoc.destroy();
                }
            } catch (e) {
                console.log('销毁PDF文档失败:', e);
            }
            this.pdfDoc = null;
        }
        
        // 清理canvas
        if (this.pdfPreviewCanvas) {
            const context = this.pdfPreviewCanvas.getContext('2d');
            context.clearRect(0, 0, this.pdfPreviewCanvas.width, this.pdfPreviewCanvas.height);
        }
        
        // 重置加载状态
        this.pdfLoading = false;
        this.isRendering = false;
        
        console.log('PDF资源清理完成');
    }

    // PDF Preview Methods
    showPdfPreview() {
        if (!this.uploadedFiles.pdf) {
            this.showError('请先上传PDF文件');
            return;
        }
        
        console.log('显示PDF预览模态框');
        
        // Get or create modal instance
        let modal = bootstrap.Modal.getInstance(this.pdfPreviewModal);
        if (!modal) {
            modal = new bootstrap.Modal(this.pdfPreviewModal);
        }
        
        // Show modal - loadPdfForPreview will be triggered by the shown.bs.modal event
        modal.show();
    }

    async loadPdfForPreview() {
        try {
            console.log('开始加载PDF预览');
            
            // 检查是否已经在加载中，避免重复加载
            if (this.pdfLoading) {
                console.log('PDF已在加载中，跳过重复加载');
                return;
            }
            
            // 设置加载状态
            this.pdfLoading = true;
            
            // 确保canvas元素存在
            if (!this.pdfPreviewCanvas) {
                console.error('PDF预览canvas元素不存在');
                this.showError('PDF预览canvas元素不存在');
                this.pdfLoading = false;
                return;
            }
            
            console.log('Canvas元素存在，尺寸:', this.pdfPreviewCanvas.width, 'x', this.pdfPreviewCanvas.height);
            
            // 显示加载提示
            const context = this.pdfPreviewCanvas.getContext('2d');
            context.clearRect(0, 0, this.pdfPreviewCanvas.width, this.pdfPreviewCanvas.height);
            context.font = '16px Arial';
            context.fillStyle = '#666';
            context.textAlign = 'center';
            context.fillText('正在加载PDF...', this.pdfPreviewCanvas.width / 2, this.pdfPreviewCanvas.height / 2);
            
            // Load PDF.js library if not already loaded
            if (typeof pdfjsLib === 'undefined') {
                console.log('加载PDF.js库');
                await this.loadPdfJsLibrary();
            }

            // Get PDF file - 使用API端点而不是直接使用URL
            let pdfUrl;
            if (this.uploadedFiles.pdf.url) {
                pdfUrl = this.uploadedFiles.pdf.url;
            } else {
                // 如果没有URL，构建一个
                const bookName = this.uploadedFiles.pdf.book_name || this.getCurrentBookName();
                // 对书名和文件名进行正确的URL编码
                const encodedBookName = encodeURIComponent(bookName);
                const encodedFileName = encodeURIComponent(this.uploadedFiles.pdf.name);
                pdfUrl = `/api/input-file/${encodedBookName}/${encodedFileName}`;
            }
            
            console.log('PDF预览URL:', pdfUrl);
            
            // 获取PDF文件
            const response = await fetch(pdfUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const arrayBuffer = await response.arrayBuffer();
            console.log('PDF文件获取成功，大小:', arrayBuffer.byteLength, '字节');
            
            // Load PDF document
            const loadingTask = pdfjsLib.getDocument({data: arrayBuffer});
            this.pdfDoc = await loadingTask.promise;
            console.log('PDF文档加载成功，页数:', this.pdfDoc ? this.pdfDoc.numPages : '未知');
            
            // Update page jump input max value - check if element exists first
            if (this.pdfPageJump && this.pdfDoc) {
                this.pdfPageJump.max = this.pdfDoc.numPages;
                this.pdfPageJump.value = 1;
            }
            
            // Render first page
            console.log('开始渲染第一页');
            await this.renderPdfPage();
            console.log('第一页渲染完成');
            
            // 重置加载状态
            this.pdfLoading = false;
        } catch (error) {
            console.error('Error loading PDF for preview:', error);
            this.showError(`PDF预览加载失败: ${error.message}`);
            
            // 显示错误信息在canvas上
            if (this.pdfPreviewCanvas) {
                const context = this.pdfPreviewCanvas.getContext('2d');
                context.clearRect(0, 0, this.pdfPreviewCanvas.width, this.pdfPreviewCanvas.height);
                context.font = '16px Arial';
                context.fillStyle = '#d32f2f';
                context.textAlign = 'center';
                context.fillText('PDF加载失败', this.pdfPreviewCanvas.width / 2, this.pdfPreviewCanvas.height / 2);
            }
            
            // 重置加载状态
            this.pdfLoading = false;
        }
    }

    async loadPdfJsLibrary() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.min.js';
            script.onload = () => {
                // Set worker source
                pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
                resolve();
            };
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async renderPdfPage() {
        console.log('开始渲染PDF页面，页码:', this.currentPdfPage);
        
        if (!this.pdfDoc) {
            console.error('PDF文档未加载');
            return;
        }
        
        // 检查是否正在渲染中
        if (this.isRendering) {
            console.log('正在渲染中，跳过本次渲染请求');
            return;
        }
        
        // 设置渲染状态
        this.isRendering = true;
        
        try {
            // 确保canvas元素存在
            if (!this.pdfPreviewCanvas) {
                console.error('PDF预览canvas元素不存在');
                return;
            }
            
            // 取消正在进行的渲染操作
            if (this.currentRenderTask) {
                try {
                    console.log('取消之前的渲染任务');
                    this.currentRenderTask.cancel();
                    // 等待取消操作完成
                    await new Promise(resolve => setTimeout(resolve, 100));
                } catch (e) {
                    console.log('取消渲染操作失败:', e);
                }
                this.currentRenderTask = null;
            }
            
            // Get page
            const page = await this.pdfDoc.getPage(this.currentPdfPage);
            console.log('获取页面成功，页码:', this.currentPdfPage);
            
            // Set scale
            const viewport = page.getViewport({ scale: 1.5 });
            console.log('视口尺寸:', viewport.width, 'x', viewport.height);
            
            // Prepare canvas
            const canvas = this.pdfPreviewCanvas;
            const context = canvas.getContext('2d');
            
            // 保存当前canvas尺寸
            const currentWidth = canvas.width;
            const currentHeight = canvas.height;
            
            // 设置新的canvas尺寸
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            
            // 如果尺寸变化，清除画布内容
            if (currentWidth !== canvas.width || currentHeight !== canvas.height) {
                context.clearRect(0, 0, canvas.width, canvas.height);
            }
            
            // 添加白色背景
            context.fillStyle = '#ffffff';
            context.fillRect(0, 0, canvas.width, canvas.height);
            
            // Render PDF page
            const renderContext = {
                canvasContext: context,
                viewport: viewport
            };
            
            console.log('开始渲染页面到canvas');
            this.currentRenderTask = page.render(renderContext);
            
            // 使用Promise.race来处理渲染可能被取消的情况
            try {
                await Promise.race([
                    this.currentRenderTask.promise,
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new Error('渲染超时')), 10000)
                    )
                ]);
                console.log('页面渲染完成');
            } catch (renderError) {
                if (renderError.name === 'RenderingCancelledException' || 
                    renderError.message.includes('渲染超时')) {
                    console.log('渲染被取消或超时');
                    return;
                }
                throw renderError;
            } finally {
                this.currentRenderTask = null;
            }
            
            // Update page info - check if element exists first
            if (this.pdfPageInfo && this.pdfDoc) {
                this.pdfPageInfo.textContent = `第 ${this.currentPdfPage} 页，共 ${this.pdfDoc.numPages} 页`;
            }
            
            // Update navigation buttons - check if elements exist first
            if (this.pdfPrevPageBtn) {
                this.pdfPrevPageBtn.disabled = this.currentPdfPage <= 1;
            }
            if (this.pdfNextPageBtn && this.pdfDoc) {
                this.pdfNextPageBtn.disabled = this.currentPdfPage >= this.pdfDoc.numPages;
            }
        } catch (error) {
            console.error('Error rendering PDF page:', error);
            // 如果是渲染取消错误，不显示错误信息
            if (error.name !== 'RenderingCancelledException') {
                this.showError('PDF页面渲染失败');
            }
        } finally {
            // 清除渲染状态
            this.isRendering = false;
        }
    }

    // Subtitles Preview Methods
    async showSubsPreview() {
        // 检查是否有上传的字幕文件
        if (!this.uploadedFiles.subs) {
            // 如果没有上传的字幕文件，检查是否从字幕文件选择器选择了字幕
            if (!this.subtitleFileSelect || !this.subtitleFileSelect.value) {
                this.showError('请先上传字幕文件或从字幕文件选择器中选择字幕');
                return;
            }
            
            // 从字幕文件选择器获取字幕内容
            try {
                const bookName = this.getCurrentBookName();
                const subtitleFile = this.subtitleFileSelect.value;
                
                const response = await fetch(`/api/get-subtitle-content?book_name=${encodeURIComponent(bookName)}&subtitle_filename=${encodeURIComponent(subtitleFile)}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    // 解析并显示字幕
                    this.parseAndDisplaySubtitles(data.subtitle_content);
                    
                    // 获取或创建模态框实例
                    let modal = bootstrap.Modal.getInstance(this.subsPreviewModal);
                    if (!modal) {
                        modal = new bootstrap.Modal(this.subsPreviewModal);
                    }
                    
                    // 显示模态框
                    modal.show();
                } else {
                    this.showError('字幕文件加载失败: ' + (data.message || '未知错误'));
                }
            } catch (error) {
                console.error('Error loading subtitles for preview:', error);
                this.showError('字幕预览加载失败: ' + error.message);
            }
        } else {
            // 使用上传的字幕文件
            try {
                // 获取字幕文件内容
                const response = await fetch(this.uploadedFiles.subs.url);
                const subtitleText = await response.text();
                
                // 解析并显示字幕
                this.parseAndDisplaySubtitles(subtitleText);
                
                // 获取或创建模态框实例
                let modal = bootstrap.Modal.getInstance(this.subsPreviewModal);
                if (!modal) {
                    modal = new bootstrap.Modal(this.subsPreviewModal);
                }
                
                // 显示模态框
                modal.show();
            } catch (error) {
                console.error('Error loading subtitles for preview:', error);
                this.showError('字幕预览加载失败');
            }
        }
    }

    // Config Preview Methods
    async showConfigPreview() {
        if (!this.uploadedFiles.config) {
            this.showError('请先上传PDF、音频和字幕文件，系统将自动检测配置文件');
            return;
        }

        try {
            // Fetch config file content
            const response = await fetch(this.uploadedFiles.config.url);
            const data = await response.json();
            
            if (response.ok && data.status === 'success') {
                // Display config content
                this.configPreviewContent.textContent = JSON.stringify(data.config_data, null, 2);
                
                // Get or create modal instance
                let modal = bootstrap.Modal.getInstance(this.configPreviewModal);
                if (!modal) {
                    modal = new bootstrap.Modal(this.configPreviewModal);
                }
                
                // Show modal
                modal.show();
            } else {
                this.showError('配置文件加载失败');
            }
        } catch (error) {
            console.error('Error loading config for preview:', error);
            this.showError('配置预览加载失败');
        }
    }

    // Video Preview Methods
    showVideoPreview(bookName, videoFilename) {
        // 如果直接提供了书名和视频文件名，使用这些参数
        if (bookName && videoFilename) {
            // 设置videoFileInfo
            this.videoFileInfo = {
                filename: videoFilename,
                bookName: bookName
            };
            
            // 添加日志
            this.addLogEntry(`准备预览视频: ${videoFilename}`);
        } else if (!this.videoFileInfo) {
            this.showError('没有可预览的视频文件');
            return;
        }
        
        // Get or create modal instance
        let modal = bootstrap.Modal.getInstance(this.videoPreviewModal);
        if (!modal) {
            modal = new bootstrap.Modal(this.videoPreviewModal);
        }
        
        // Show modal - loadVideoForPreview will be triggered by the shown.bs.modal event
        modal.show();
    }

    async loadVideoForPreview() {
        try {
            // 检查是否有视频文件信息
            if (!this.videoFileInfo) {
                console.log('没有找到videoFileInfo，尝试从其他地方获取视频文件信息');
                
                // 尝试从uploadedFiles中获取视频文件信息
                if (this.uploadedFiles && this.uploadedFiles.video) {
                    console.log('从uploadedFiles.video获取视频文件信息');
                    this.videoFileInfo = {
                        filename: this.uploadedFiles.video.name || this.uploadedFiles.video.filename,
                        data: this.uploadedFiles.video
                    };
                } else {
                    // 尝试构建视频文件名并获取视频文件信息
                    console.log('尝试构建视频文件名并获取视频文件信息');
                    const bookName = this.getCurrentBookName();
                    let videoFilename = '';
                    
                    // 根据字幕文件名或音频文件名构建视频文件名
                    if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
                        videoFilename = this.uploadedFiles.subs.name.replace(/\.[^/.]+$/, '') + '.mp4';
                    } else if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                        videoFilename = this.uploadedFiles.audio.name.replace(/\.[^/.]+$/, '') + '.mp4';
                    } else {
                        this.showError('无法确定视频文件名');
                        return;
                    }
                    
                    try {
                        // 调用API检查视频是否存在并获取视频文件信息
                        const response = await fetch(`/api/check-video-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(videoFilename)}`);
                        const data = await response.json();
                        
                        if (response.ok && data.exists) {
                            console.log('视频文件存在，设置videoFileInfo');
                            this.videoFileInfo = {
                                filename: videoFilename,
                                data: data
                            };
                        } else {
                            this.showError('视频文件不存在');
                            return;
                        }
                    } catch (error) {
                        console.error('获取视频文件信息失败:', error);
                        this.showError('获取视频文件信息失败');
                        return;
                    }
                }
            }
            
            const { filename, data, bookName } = this.videoFileInfo;
            const finalBookName = bookName || this.getCurrentBookName();
            
            // Set video source
            this.videoPreviewPlayer.src = `/api/video-preview/${encodeURIComponent(finalBookName)}/${encodeURIComponent(filename)}`;
            this.videoPreviewPlayer.type = 'video/mp4';
            this.videoPreviewPlayer.controls = true;
            this.videoPreviewPlayer.preload = 'metadata';
            
            // Set video info
            this.videoPreviewFilename.textContent = filename;
            this.videoPreviewFilesize.textContent = data?.filesize || '未知大小';
            this.videoPreviewTime.textContent = data?.create_time || '未知时间';
            
            // 添加日志
            this.addLogEntry(`视频预览已加载: ${filename}`);
            
            console.log('视频预览已加载:', filename);
        } catch (error) {
            console.error('Error loading video for preview:', error);
            this.showError('视频预览加载失败');
        }
    }

    parseAndDisplaySubtitles(subtitleText) {
        // Clear existing content
        this.subsPreviewTbody.innerHTML = '';
        
        // Split subtitle text by double newlines (standard SRT format)
        const subtitleBlocks = subtitleText.trim().split(/\r?\n\r?\n/);
        
        subtitleBlocks.forEach(block => {
            const lines = block.split(/\r?\n/);
            
            if (lines.length >= 3) {
                const index = lines[0];
                const timeRange = lines[1];
                const text = lines.slice(2).join('\n');
                
                // Create table row
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${index}</td>
                    <td>${timeRange}</td>
                    <td>${this.escapeHtml(text)}</td>
                `;
                
                this.subsPreviewTbody.appendChild(row);
            }
        });
        
        // If no valid subtitles found
        if (this.subsPreviewTbody.children.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td colspan="3" class="text-center text-muted">
                    未找到有效的字幕内容
                </td>
            `;
            this.subsPreviewTbody.appendChild(row);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 打开本地目录方法
    async openLocalDirectory() {
        try {
            // 获取书名
            const bookName = this.getCurrentBookName();
            
            // 调用API打开本地目录
            const response = await fetch(`/api/open-directory/${encodeURIComponent(bookName)}`, {
                method: 'GET'
            });

            const data = await response.json();

            if (response.ok) {
                if (data.success) {
                    this.showSuccess(`已打开本地目录: ${data.path}`);
                } else {
                    this.showError(`打开目录失败: ${data.message}`);
                }
            } else {
                throw new Error(data.error || '打开目录失败');
            }
        } catch (error) {
            console.error('打开本地目录错误:', error);
            this.showError(`打开本地目录失败: ${error.message}`);
        }
    }

    // Audio Player Methods
    playAudio() {
        if (!this.uploadedFiles.audio) {
            this.showError('请先上传音频文件');
            return;
        }

        // 显示悬浮播放器
        this.showAudioHoverPlayer();
    }

    closeAudioPlayer() {
        // Pause audio if playing
        this.audioPlayer.pause();
        
        // Hide audio player container
        this.audioPlayerContainer.style.display = 'none';
    }

    // Audio Hover Player Methods
    showAudioHoverPlayer() {
        if (!this.uploadedFiles.audio) {
            return;
        }

        // 确保获取最新的音频文件名元素
        const audioFilenameElement = document.getElementById('audio-file-name');
        if (!audioFilenameElement) {
            console.error('找不到音频文件名元素');
            return;
        }

        // 计算预览窗口位置
        const rect = audioFilenameElement.getBoundingClientRect();
        const previewWidth = 300;  // 预览窗口宽度，与HTML中设置的宽度一致
        
        // 计算水平位置，确保不超出屏幕右边界
        let leftPos = rect.left;
        if (leftPos + previewWidth > window.innerWidth) {
            leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
        }
        
        // 计算垂直位置，优先显示在下方
        let topPos = rect.bottom + 5; // 添加5px间距
        
        // 应用计算的位置
        this.audioHoverPlayer.style.top = topPos + 'px';
        this.audioHoverPlayer.style.left = leftPos + 'px';
        
        // Show hover player
        this.audioHoverPlayer.style.display = 'block';
        
        // Set audio source
        this.audioHoverPlayerElement.src = this.uploadedFiles.audio.url;
        
        // Reset any existing timeout
        clearTimeout(this.audioHoverTimeout);
        
        console.log('音频悬浮播放器已显示');
    }

    hideAudioHoverPlayer() {
        // 如果预览窗体被固定，则不隐藏
        if (this.audioHoverPinned) {
            return;
        }
        
        // Set timeout to hide the player
        this.audioHoverTimeout = setTimeout(() => {
            // Pause audio if playing
            this.audioHoverPlayerElement.pause();
            
            // Hide hover player
            this.audioHoverPlayer.style.display = 'none';
        }, 100);
    }

    // Toggle audio hover player pin state
    toggleAudioHoverPin() {
        this.audioHoverPinned = !this.audioHoverPinned;
        
        // Update pin button appearance
        if (this.audioHoverPinned) {
            this.audioPinBtn.classList.remove('btn-outline-secondary');
            this.audioPinBtn.classList.add('btn-primary');
            this.audioPinBtn.innerHTML = '<i class="bi bi-pin-fill"></i>';
            this.audioPinBtn.title = '取消固定';
        } else {
            this.audioPinBtn.classList.remove('btn-primary');
            this.audioPinBtn.classList.add('btn-outline-secondary');
            this.audioPinBtn.innerHTML = '<i class="bi bi-pin"></i>';
            this.audioPinBtn.title = '固定';
        }
    }

    // Close audio hover player
    closeAudioHoverPlayer() {
        // Pause audio if playing
        this.audioHoverPlayerElement.pause();
        
        // Hide hover player
        this.audioHoverPlayer.style.display = 'none';
        
        // Reset pin state
        if (this.audioHoverPinned) {
            this.toggleAudioHoverPin();
        }
    }

    // PDF Hover Preview Methods
    showPdfHoverPreview() {
        if (!this.uploadedFiles.pdf) {
            return;
        }

        // 计算预览窗口位置
        const rect = this.pdfFilenameHover.getBoundingClientRect();
        const previewWidth = 400;  // 预览窗口宽度
        const previewHeight = 250; // 预览窗口高度
        
        // 计算水平位置，确保不超出屏幕右边界
        let leftPos = rect.left + window.scrollX;
        if (leftPos + previewWidth > window.innerWidth) {
            leftPos = window.innerWidth - previewWidth - 10; // 留10px边距
        }
        
        // 计算垂直位置，优先显示在下方，如果空间不够则显示在上方
        let topPos;
        const spaceBelow = window.innerHeight - rect.bottom;
        const spaceAbove = rect.top;
        
        if (spaceBelow > previewHeight + 10) {
            // 下方空间足够，显示在下方
            topPos = rect.bottom + window.scrollY;
        } else if (spaceAbove > previewHeight + 10) {
            // 上方空间足够，显示在上方
            topPos = rect.top + window.scrollY - previewHeight;
        } else {
            // 两处空间都不够，选择空间较大的一方
            if (spaceBelow >= spaceAbove) {
                topPos = rect.bottom + window.scrollY;
            } else {
                topPos = rect.top + window.scrollY - previewHeight;
            }
        }
        
        // 应用计算的位置
        this.pdfHoverPreview.style.top = topPos + 'px';
        this.pdfHoverPreview.style.left = leftPos + 'px';
        
        // Show hover preview
        this.pdfHoverPreview.style.display = 'block';
        
        // Set PDF source with toolbar disabled
        const bookName = this.getCurrentBookName();
        const filename = this.uploadedFiles.pdf.name || this.uploadedFiles.pdf.filename;
        // 添加参数以隐藏PDF查看器的工具栏
        this.pdfHoverPreviewElement.src = `/api/pdf-preview/${bookName}/${filename}#toolbar=0&navpanes=0&scrollbar=0`;
        
        // Reset any existing timeout
        clearTimeout(this.pdfHoverTimeout);
    }

    hidePdfHoverPreview() {
        // Set timeout to hide the preview
        this.pdfHoverTimeout = setTimeout(() => {
            // Hide hover preview
            this.pdfHoverPreview.style.display = 'none';
        }, 100);
    }

    // Subtitle Hover Preview Methods
    showSubsHoverPreview() {
        if (!this.uploadedFiles.subs) {
            return;
        }

        // Show hover preview
        this.subsHoverPreview.style.display = 'block';
        
        // Load subtitle content
        const filename = this.uploadedFiles.subs.name || this.uploadedFiles.subs.filename;
        this.loadSubtitleContent(filename, this.subsHoverPreviewElement);
        
        // Reset any existing timeout
        clearTimeout(this.subsHoverTimeout);
    }

    hideSubsHoverPreview() {
        // Set timeout to hide the preview
        this.subsHoverTimeout = setTimeout(() => {
            // Hide hover preview
            this.subsHoverPreview.style.display = 'none';
        }, 100);
    }

    async loadSubtitleContentForPreview(filename, contentElement) {
        try {
            console.log('=== 悬浮预览 loadSubtitleContent 被调用 ===');
            console.log('filename:', filename);
            console.log('contentElement:', contentElement);

            if (!filename) {
                if (contentElement) {
                    contentElement.textContent = '没有可预览的字幕文件';
                }
                return;
            }

            // 显示加载状态
            if (contentElement) {
                contentElement.textContent = '加载中...';
                contentElement.style.whiteSpace = 'normal';
                contentElement.style.fontFamily = 'inherit';
                contentElement.style.fontSize = 'inherit';
                contentElement.style.lineHeight = 'inherit';
                contentElement.style.color = '#666';
                contentElement.style.overflowY = 'hidden';
                contentElement.style.maxHeight = 'none';
            }

            const bookName = this.getCurrentBookName();
            console.log('loadSubtitleContent - 书名:', bookName, '字幕文件名:', filename);

            // 如果无法获取书名，尝试从字幕文件名中提取
            let finalBookName = bookName;
            if (!finalBookName && filename) {
                // 尝试从字幕文件名中提取书名
                if (filename.includes('红楼梦')) {
                    finalBookName = '红楼梦';
                    console.log('从字幕文件名中提取书名:', finalBookName);
                }
            }

            if (!finalBookName) {
                if (contentElement) {
                    contentElement.textContent = '无法确定书名，无法加载字幕内容';
                }
                return;
            }

            // 首先尝试使用原始文件名，如果失败则尝试使用其他可能的键
            const possibleKeys = [filename];

            // 如果是中文文件名，secure_filename可能会将其简化为'srt'
            if (/[\u4e00-\u9fff]/.test(filename) && filename.endsWith('.srt')) {
                possibleKeys.push('srt');
            }

            // 如果文件名包含特殊字符，尝试只保留基本字符和扩展名
            if (!/^[a-zA-Z0-9_.-]+$/.test(filename)) {
                const baseName = filename.replace(/^.*[\\\/]/, '').replace(/\.[^.]*$/, '');
                possibleKeys.push(baseName.replace(/[^a-zA-Z0-9_.-]/g, '_') + '.srt');
            }

            console.log('尝试可能的文件键:', possibleKeys);

            let subtitleText = null;
            let lastError = null;

            // 逐一尝试可能的键
            for (const tryKey of possibleKeys) {
                try {
                    const apiUrl = `/api/subs-content/${encodeURIComponent(finalBookName)}/${encodeURIComponent(tryKey)}`;
                    console.log(`尝试API请求URL: ${apiUrl}`);

                    const response = await fetch(apiUrl);

                    if (response.ok) {
                        const subtitleData = await response.json();
                        console.log('API响应数据:', subtitleData);

                        if (subtitleData.content) {
                            subtitleText = subtitleData.content;
                            console.log(`成功使用键: ${tryKey}`);
                            break;
                        } else if (subtitleData.error) {
                            lastError = subtitleData.error;
                        }
                    } else {
                        lastError = `HTTP ${response.status}: ${response.statusText}`;
                    }
                } catch (error) {
                    console.error(`尝试键 ${tryKey} 失败:`, error);
                    lastError = error.message;
                }
            }

            if (!subtitleText) {
                throw new Error(`无法加载字幕内容，已尝试: ${possibleKeys.join(', ')}. 最后错误: ${lastError}`);
            }

            // Display subtitle content
            if (contentElement) {
                // 直接显示原始字幕内容，不进行额外处理
                // 保留字幕的原始格式，包括时间戳和序号
                contentElement.textContent = subtitleText;
                
                // 确保内容元素使用正确的样式
                contentElement.style.whiteSpace = 'pre-wrap';
                contentElement.style.fontFamily = 'monospace';
                contentElement.style.fontSize = '12px';
                contentElement.style.lineHeight = '1.4';
                contentElement.style.color = '#333';
                contentElement.style.overflowY = 'auto';
                contentElement.style.maxHeight = '120px';
            }
            
            console.log('字幕内容已加载:', filename);
        } catch (error) {
            console.error('Error loading subtitle content:', error);
            if (contentElement) {
                contentElement.textContent = '字幕内容加载失败: ' + error.message;
                contentElement.style.whiteSpace = 'normal';
                contentElement.style.fontFamily = 'inherit';
                contentElement.style.fontSize = 'inherit';
                contentElement.style.lineHeight = 'inherit';
                contentElement.style.color = '#d32f2f';
                contentElement.style.overflowY = 'hidden';
                contentElement.style.maxHeight = 'none';
            }
        }
    }

    // Config Hover Preview Methods
    showConfigHoverPreview() {
        if (!this.uploadedFiles.config) {
            return;
        }

        // Show hover preview
        this.configHoverPreview.style.display = 'block';
        
        // Load config content
        this.loadConfigContent();
        
        // Reset any existing timeout
        clearTimeout(this.configHoverTimeout);
    }

    hideConfigHoverPreview() {
        // Set timeout to hide the preview
        this.configHoverTimeout = setTimeout(() => {
            // Hide hover preview
            this.configHoverPreview.style.display = 'none';
        }, 100);
    }

    async loadConfigContentForUpload(contentElement) {
        try {
            if (!this.uploadedFiles.config) {
                contentElement.textContent = '没有可预览的配置文件';
                return;
            }
            
            const bookName = this.getCurrentBookName();
            // 使用实际上传的文件名，而不是硬编码为'config'
            const filename = this.uploadedFiles.config.name || this.uploadedFiles.config.filename || 'config';
            
            console.log('尝试加载配置内容:', bookName, filename);
            
            // Fetch config content
            const response = await fetch(`/api/config-content/${bookName}/${filename}`);
            
            console.log('配置内容API响应状态:', response.status);
            
            if (!response.ok) {
                throw new Error('配置内容加载失败');
            }
            
            // 尝试解析为JSON，如果失败则作为文本处理
            let configText;
            const contentType = response.headers.get('content-type');
            console.log('响应内容类型:', contentType);
            
            if (contentType && contentType.includes('application/json')) {
                const configData = await response.json();
                configText = JSON.stringify(configData, null, 2);
            } else {
                configText = await response.text();
            }
            
            // Display config content
            contentElement.textContent = configText;
            
            console.log('配置内容已加载:', filename);
        } catch (error) {
            console.error('Error loading config content:', error);
            contentElement.textContent = '配置内容加载失败: ' + error.message;
        }
    }

    async loadConfigContent() {
        try {
            if (!this.uploadedFiles.config) {
                this.configHoverPreviewElement.textContent = '没有可预览的配置文件';
                return;
            }
            
            const bookName = this.getCurrentBookName();
            const filename = this.uploadedFiles.config.name || this.uploadedFiles.config.filename || 'config';
            
            // Fetch config content
            const response = await fetch(`/api/config-content/${bookName}/${filename}`);
            
            if (!response.ok) {
                throw new Error('配置内容加载失败');
            }
            
            // 尝试解析为JSON，如果失败则作为文本处理
            let configText;
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const configData = await response.json();
                configText = JSON.stringify(configData, null, 2);
            } else {
                configText = await response.text();
            }
            
            // Display config content
            this.configHoverPreviewElement.textContent = configText;
            
            console.log('配置内容已加载:', filename);
        } catch (error) {
            console.error('Error loading config content:', error);
            this.configHoverPreviewElement.textContent = '配置内容加载失败';
        }
    }

    // Video Hover Preview Methods
    async showVideoHoverPreview() {
        // 检查是否有视频文件信息
        if (!this.uploadedFiles.video) {
            console.log('没有找到uploadedFiles.video，尝试从其他地方获取视频文件信息');
            
            // 尝试构建视频文件名
            const bookName = this.getCurrentBookName();
            let videoFilename = '';
            
            // 根据字幕文件名或音频文件名构建视频文件名
            if (this.uploadedFiles.subs && this.uploadedFiles.subs.name) {
                videoFilename = this.uploadedFiles.subs.name.replace(/\.[^/.]+$/, '') + '.mp4';
            } else if (this.uploadedFiles.audio && this.uploadedFiles.audio.name) {
                videoFilename = this.uploadedFiles.audio.name.replace(/\.[^/.]+$/, '') + '.mp4';
            } else {
                console.log('无法确定视频文件名，跳过悬浮预览');
                return;
            }
            
            try {
                // 调用API检查视频是否存在
                const response = await fetch(`/api/check-video-exists/${encodeURIComponent(bookName)}/${encodeURIComponent(videoFilename)}`);
                const data = await response.json();
                
                if (response.ok && data.exists) {
                    console.log('视频文件存在，设置uploadedFiles.video');
                    this.uploadedFiles.video = {
                        filename: videoFilename
                    };
                } else {
                    console.log('视频文件不存在，跳过悬浮预览');
                    return;
                }
            } catch (error) {
                console.error('获取视频文件信息失败:', error);
                return;
            }
        }

        // Show hover preview
        this.videoHoverPreview.style.display = 'block';
        
        // Set video source
        const bookName = this.getCurrentBookName();
        const filename = this.uploadedFiles.video.name || this.uploadedFiles.video.filename;
        this.videoHoverPreviewElement.src = `/api/video-preview/${bookName}/${filename}`;
        this.videoHoverPreviewElement.type = 'video/mp4';
        this.videoHoverPreviewElement.controls = true;
        this.videoHoverPreviewElement.preload = 'metadata';
        
        // Reset any existing timeout
        clearTimeout(this.videoHoverTimeout);
    }

    hideVideoHoverPreview() {
        // Set timeout to hide the preview
        this.videoHoverTimeout = setTimeout(() => {
            // Pause video if playing
            this.videoHoverPreviewElement.pause();
            
            // Hide hover preview
            this.videoHoverPreview.style.display = 'none';
        }, 100);
    }

    // Transition Effect Preview Methods
    previewTransitionEffect() {
        // Get selected transition effect
        const selectedEffect = this.transitionEffect.value;

        // Get preview container and pages
        const previewContainer = document.getElementById('transition-preview-container');
        const leftPage = document.getElementById('preview-page-left');
        const rightPage = document.getElementById('preview-page-right');
        const flipOverlay = document.getElementById('page-flip-overlay');

        if (!previewContainer || !leftPage || !rightPage || !flipOverlay) {
            console.error('预览容器元素不存在');
            return;
        }

        // Show the preview container
        previewContainer.style.display = 'block';

        // Reset any existing animations
        this.resetPageAnimations();

        // Add book container class for opening animation
        const bookContainer = previewContainer.querySelector('div[style*="perspective"]');
        if (bookContainer) {
            bookContainer.classList.add('book-container');
        }

        // Set initial page content
        this.updatePageContent(leftPage, '第 1 页', '左页内容示例\n这里是书本的第一页内容');
        this.updatePageContent(rightPage, '第 2 页', '右页内容示例\n这里是书本的第二页内容');
        this.updatePageContent(flipOverlay, '第 3 页', '新页内容\n这是翻开后显示的新页面');

        // Force reflow to reset animations
        void leftPage.offsetWidth;
        void rightPage.offsetWidth;
        void flipOverlay.offsetWidth;

        // Apply animation based on selected effect
        switch(selectedEffect) {
            case 'turn-js':
                this.animateBookPageTurn(leftPage, rightPage, flipOverlay);
                break;
            case 'fade':
                this.animateBookFade(leftPage, rightPage, flipOverlay);
                break;
            case 'slide':
                this.animateBookSlide(leftPage, rightPage, flipOverlay);
                break;
            case 'flip':
                this.animateBookFlip(leftPage, rightPage, flipOverlay);
                break;
            case 'zoom':
                this.animateBookZoom(leftPage, rightPage, flipOverlay);
                break;
            case 'wipe':
                this.animateBookWipe(leftPage, rightPage, flipOverlay);
                break;
            case 'cube':
                this.animateBookCube(leftPage, rightPage, flipOverlay);
                break;
            case 'page-curl':
                this.animateBookPageCurl(leftPage, rightPage, flipOverlay);
                break;
            case 'accordion':
                this.animateBookAccordion(leftPage, rightPage, flipOverlay);
                break;
            case 'ripple':
                this.animateBookRipple(leftPage, rightPage, flipOverlay);
                break;
            default:
                // Default to book page turn
                this.animateBookPageTurn(leftPage, rightPage, flipOverlay);
        }
    }

    // Helper method to reset page animations
    resetPageAnimations() {
        const leftPage = document.getElementById('preview-page-left');
        const rightPage = document.getElementById('preview-page-right');
        const flipOverlay = document.getElementById('page-flip-overlay');

        [leftPage, rightPage, flipOverlay].forEach(page => {
            if (page) {
                page.style.animation = 'none';
                page.style.transform = 'none';
                page.style.opacity = '1';
                page.classList.remove('turn-effect');
            }
        });

        // Reset overlay visibility
        if (flipOverlay) {
            flipOverlay.style.opacity = '0';
            flipOverlay.style.transform = 'rotateY(0deg)';
        }
    }

    // Helper method to update page content
    updatePageContent(pageElement, pageNumber, textContent) {
        if (!pageElement) return;

        const pageContent = pageElement.querySelector('.page-content');
        if (pageContent) {
            const pageNumElement = pageContent.querySelector('.page-number');
            const textElement = pageContent.querySelector('.sample-text');

            if (pageNumElement) pageNumElement.textContent = pageNumber;
            if (textElement) textElement.textContent = textContent;
        }
    }

    // Book page turn animation (center axis)
    animateBookPageTurn(leftPage, rightPage, flipOverlay) {
        // Start with overlay visible
        flipOverlay.style.opacity = '1';
        flipOverlay.style.transform = 'rotateY(0deg)';

        // Animate the page flip from center
        setTimeout(() => {
            flipOverlay.style.transition = 'transform 1.5s ease-in-out';
            flipOverlay.style.transform = 'rotateY(-180deg)';
        }, 100);

        // Reset after animation
        setTimeout(() => {
            flipOverlay.style.transition = 'none';
            this.resetPageAnimations();
        }, 2000);
    }

    // Book fade animation
    animateBookFade(leftPage, rightPage, flipOverlay) {
        // Fade out current pages
        leftPage.style.transition = 'opacity 1s ease-in-out';
        rightPage.style.transition = 'opacity 1s ease-in-out';
        leftPage.style.opacity = '0.3';
        rightPage.style.opacity = '0.3';

        // Show overlay with fade in
        flipOverlay.style.opacity = '0';
        flipOverlay.style.transition = 'opacity 1s ease-in-out';
        setTimeout(() => {
            flipOverlay.style.opacity = '1';
        }, 500);

        // Reset after animation
        setTimeout(() => {
            this.resetPageAnimations();
        }, 2000);
    }

    // Book slide animation
    animateBookSlide(leftPage, rightPage, flipOverlay) {
        // Slide current pages out
        leftPage.style.transition = 'transform 1s ease-in-out';
        rightPage.style.transition = 'transform 1s ease-in-out';
        leftPage.style.transform = 'translateX(-100%)';
        rightPage.style.transform = 'translateX(100%)';

        // Slide overlay in from center
        flipOverlay.style.transform = 'translateX(0) scale(1)';
        flipOverlay.style.transition = 'transform 1s ease-in-out';

        // Reset after animation
        setTimeout(() => {
            this.resetPageAnimations();
        }, 2000);
    }

    // Book flip animation
    animateBookFlip(leftPage, rightPage, flipOverlay) {
        // Add 3D flip effect to right page
        rightPage.style.transition = 'transform 1.2s ease-in-out';
        rightPage.style.transform = 'rotateY(-180deg)';

        // Show overlay as the backside
        setTimeout(() => {
            flipOverlay.style.opacity = '1';
            flipOverlay.style.transform = 'rotateY(0deg)';
        }, 600);

        // Reset after animation
        setTimeout(() => {
            this.resetPageAnimations();
        }, 2000);
    }

    // Book zoom animation
    animateBookZoom(leftPage, rightPage, flipOverlay) {
        // Zoom out current pages
        leftPage.style.transition = 'transform 1s ease-in-out';
        rightPage.style.transition = 'transform 1s ease-in-out';
        leftPage.style.transform = 'scale(0.8)';
        rightPage.style.transform = 'scale(0.8)';
        leftPage.style.opacity = '0.5';
        rightPage.style.opacity = '0.5';

        // Zoom in overlay
        flipOverlay.style.transform = 'scale(0)';
        flipOverlay.style.opacity = '0';
        flipOverlay.style.transition = 'all 1s ease-in-out';

        setTimeout(() => {
            flipOverlay.style.transform = 'scale(1)';
            flipOverlay.style.opacity = '1';
        }, 300);

        // Reset after animation
        setTimeout(() => {
            this.resetPageAnimations();
        }, 2000);
    }

    // Book wipe animation
    animateBookWipe(leftPage, rightPage, flipOverlay) {
        // Create wipe effect from center
        flipOverlay.style.clipPath = 'inset(0 50% 0 0)';
        flipOverlay.style.opacity = '1';
        flipOverlay.style.transition = 'clip-path 1.2s ease-in-out';

        setTimeout(() => {
            flipOverlay.style.clipPath = 'inset(0 0 0 0)';
        }, 100);

        // Reset after animation
        setTimeout(() => {
            flipOverlay.style.transition = 'none';
            this.resetPageAnimations();
        }, 2000);
    }

    // Book cube animation
    animateBookCube(leftPage, rightPage, flipOverlay) {
        // Create cube rotation effect
        const container = leftPage.parentElement;
        container.style.transformStyle = 'preserve-3d';
        container.style.transition = 'transform 1.5s ease-in-out';

        // Animate the entire book container
        setTimeout(() => {
            container.style.transform = 'rotateY(-90deg)';
        }, 100);

        // Reset after animation
        setTimeout(() => {
            container.style.transition = 'none';
            container.style.transform = 'rotateY(0deg)';
            this.resetPageAnimations();
        }, 2000);
    }

    // Book page curl animation
    animateBookPageCurl(leftPage, rightPage, flipOverlay) {
        // Create page curl effect on right page
        rightPage.style.transition = 'transform 1.5s ease-in-out';
        rightPage.style.transform = 'perspective(1000px) rotateY(-90deg)';
        rightPage.style.transformOrigin = 'left center';

        // Show curl shadow
        rightPage.style.boxShadow = '-20px 0 40px rgba(0,0,0,0.4)';

        // Reveal overlay
        setTimeout(() => {
            flipOverlay.style.opacity = '1';
            flipOverlay.style.transform = 'rotateY(0deg)';
        }, 750);

        // Reset after animation
        setTimeout(() => {
            rightPage.style.boxShadow = 'inset 0 0 20px rgba(0,0,0,0.1)';
            this.resetPageAnimations();
        }, 2500);
    }

    // Book accordion animation
    animateBookAccordion(leftPage, rightPage, flipOverlay) {
        // Create accordion effect
        leftPage.style.transition = 'transform 1s ease-in-out';
        rightPage.style.transition = 'transform 1s ease-in-out';

        // Fold pages like accordion
        leftPage.style.transform = 'scaleX(0.3)';
        setTimeout(() => {
            rightPage.style.transform = 'scaleX(0.3)';
        }, 200);

        // Expand overlay
        setTimeout(() => {
            flipOverlay.style.opacity = '1';
            flipOverlay.style.transform = 'scaleX(1)';
            flipOverlay.style.transition = 'transform 0.5s ease-in-out';
        }, 700);

        // Reset after animation
        setTimeout(() => {
            this.resetPageAnimations();
        }, 2000);
    }

    // Book ripple animation
    animateBookRipple(leftPage, rightPage, flipOverlay) {
        // Create ripple effect from center
        const ripple = document.createElement('div');
        ripple.style.cssText = `
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            background: radial-gradient(circle, rgba(255,255,255,0.8) 0%, transparent 70%);
            border-radius: 50%;
            transform: translate(-50%, -50%);
            z-index: 10;
        `;

        leftPage.appendChild(ripple);

        // Animate ripple
        ripple.style.transition = 'all 1s ease-out';
        setTimeout(() => {
            ripple.style.width = '600px';
            ripple.style.height = '600px';
            ripple.style.opacity = '0';
        }, 100);

        // Show overlay after ripple
        setTimeout(() => {
            flipOverlay.style.opacity = '1';
            leftPage.removeChild(ripple);
        }, 1200);

        // Reset after animation
        setTimeout(() => {
            this.resetPageAnimations();
        }, 2500);
    }
    
    /**
     * 预览页面设置中的翻页动画效果（重新设计版本）
     */
    previewPageSettingsTransition() {
        // 获取选择的翻页效果
        const transitionEffect = document.getElementById('transition-effect');
        const selectedEffect = transitionEffect ? transitionEffect.value : 'turn-js';

        // 获取页面设置预览容器
        const container = document.getElementById('page-settings-preview-canvas').parentElement;

        // 如果容器不存在，则返回
        if (!container) return;

        // 获取当前画布内容作为页面内容
        const canvas = document.getElementById('page-settings-preview-canvas');
        const canvasDataUrl = canvas.toDataURL();

        // 获取竖排双页模式设置
        const verticalLayout = document.getElementById('vertical-layout');
        const isVerticalLayout = verticalLayout && verticalLayout.checked;

        // 获取页面排列顺序设置
        const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
        const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;

        // 清除之前的翻页效果
        if (window.pageSettingsFlipEffect) {
            window.pageSettingsFlipEffect.destroy();
            window.pageSettingsFlipEffect = null;
        }

        // 清除之前的翻页容器
        const existingFlipContainer = document.getElementById('page-settings-flip-container');
        if (existingFlipContainer) {
            existingFlipContainer.remove();
        }

        // 隐藏原始canvas
        canvas.style.display = 'none';

        // 如果是竖排双页模式，显示两页预览
        if (isVerticalLayout) {
            this.createDoublePagePreview(container, canvasDataUrl, selectedEffect, isOddRightEvenLeft);
        } else {
            // 单页模式，显示翻页效果
            this.createSinglePagePreview(container, canvasDataUrl, selectedEffect);
        }
    }

    /**
     * 创建双页预览（竖排双页模式）- 使用真实Canvas元素
     */
    createDoublePagePreview(container, canvasDataUrl, selectedEffect, isOddRightEvenLeft) {
        const bookContainer = document.createElement('div');
        bookContainer.id = 'page-settings-flip-container';
        bookContainer.style.cssText = `
            width: 100%;
            height: 500px;
            position: relative;
            display: flex;
            perspective: 1000px;
            background: #f5f5f5;
            border-radius: 8px;
            overflow: hidden;
        `;

        // 隐藏原始canvas
        const originalCanvas = document.getElementById('page-settings-preview-canvas');
        originalCanvas.style.display = 'none';

        // 创建左页Canvas
        const leftCanvas = document.createElement('canvas');
        leftCanvas.className = 'settings-book-canvas left-canvas';
        leftCanvas.style.cssText = `
            position: relative;
            width: 50%;
            height: 100%;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.1);
            transform-origin: right center;
            border-right: 1px solid #ddd;
        `;

        // 创建右页Canvas
        const rightCanvas = document.createElement('canvas');
        rightCanvas.className = 'settings-book-canvas right-canvas';
        rightCanvas.style.cssText = `
            position: relative;
            width: 50%;
            height: 100%;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.1);
            transform-origin: left center;
        `;

        // 设置Canvas尺寸
        const containerWidth = bookContainer.offsetWidth || 800;
        const containerHeight = 500;

        leftCanvas.width = containerWidth / 2;
        leftCanvas.height = containerHeight;
        rightCanvas.width = containerWidth / 2;
        rightCanvas.height = containerHeight;

        // 将页面添加到容器
        bookContainer.appendChild(leftCanvas);
        bookContainer.appendChild(rightCanvas);

        container.appendChild(bookContainer);

        // 渲染PDF内容到Canvas
        this.renderDoublePageToCanvases(leftCanvas, rightCanvas, isOddRightEvenLeft);

        // 添加页面标识
        this.addPageLabelsToCanvases(leftCanvas, rightCanvas, isOddRightEvenLeft);

        // 添加书本打开动画
        bookContainer.style.animation = 'bookOpen 1s ease-out';

        // 根据选择的翻页效果应用动画
        setTimeout(() => {
            this.applyLogicalPageTurn(selectedEffect, leftCanvas, rightCanvas, bookContainer, isOddRightEvenLeft);
        }, 1500);
    }

    /**
     * 渲染双页到Canvas元素
     */
    async renderDoublePageToCanvases(leftCanvas, rightCanvas, isOddRightEvenLeft) {
        if (!this.pageSettingsPdfDoc) return;

        const currentPage = this.currentPageSettingsPage || 1;
        let leftPageNum, rightPageNum;

        // 根据页面排列顺序确定页码
        if (isOddRightEvenLeft) {
            // 奇数页在右侧，偶数页在左侧
            rightPageNum = currentPage % 2 === 1 ? currentPage : currentPage + 1;
            leftPageNum = rightPageNum - 1;
        } else {
            // 奇数页在左侧，偶数页在右侧
            leftPageNum = currentPage % 2 === 1 ? currentPage : currentPage + 1;
            rightPageNum = leftPageNum + 1;
        }

        // 确保页码有效
        leftPageNum = Math.max(1, Math.min(leftPageNum, this.pageSettingsPdfDoc.numPages));
        rightPageNum = Math.max(1, Math.min(rightPageNum, this.pageSettingsPdfDoc.numPages));

        try {
            // 渲染左页
            const leftPage = await this.pageSettingsPdfDoc.getPage(leftPageNum);
            const leftViewport = leftPage.getViewport({ scale: 1.5 });
            const leftContext = leftCanvas.getContext('2d');

            // 清除左页Canvas
            leftContext.clearRect(0, 0, leftCanvas.width, leftCanvas.height);

            // 计算左页缩放和位置
            const leftScale = Math.min(leftCanvas.width / leftViewport.width, leftCanvas.height / leftViewport.height);
            const leftScaledWidth = leftViewport.width * leftScale;
            const leftScaledHeight = leftViewport.height * leftScale;
            const leftX = (leftCanvas.width - leftScaledWidth) / 2;
            const leftY = (leftCanvas.height - leftScaledHeight) / 2;

            leftContext.save();
            leftContext.translate(leftX, leftY);
            leftContext.scale(leftScale, leftScale);

            const leftRenderTask = leftPage.render({
                canvasContext: leftContext,
                viewport: leftViewport
            });
            await leftRenderTask.promise;
            leftContext.restore();

            // 渲染右页
            const rightPage = await this.pageSettingsPdfDoc.getPage(rightPageNum);
            const rightViewport = rightPage.getViewport({ scale: 1.5 });
            const rightContext = rightCanvas.getContext('2d');

            // 清除右页Canvas
            rightContext.clearRect(0, 0, rightCanvas.width, rightCanvas.height);

            // 计算右页缩放和位置
            const rightScale = Math.min(rightCanvas.width / rightViewport.width, rightCanvas.height / rightViewport.height);
            const rightScaledWidth = rightViewport.width * rightScale;
            const rightScaledHeight = rightViewport.height * rightScale;
            const rightX = (rightCanvas.width - rightScaledWidth) / 2;
            const rightY = (rightCanvas.height - rightScaledHeight) / 2;

            rightContext.save();
            rightContext.translate(rightX, rightY);
            rightContext.scale(rightScale, rightScale);

            const rightRenderTask = rightPage.render({
                canvasContext: rightContext,
                viewport: rightViewport
            });
            await rightRenderTask.promise;
            rightContext.restore();

        } catch (error) {
            console.error('渲染双页失败:', error);
            // 显示错误信息
            [leftCanvas, rightCanvas].forEach(canvas => {
                const context = canvas.getContext('2d');
                context.fillStyle = '#ff0000';
                context.font = '16px Arial';
                context.textAlign = 'center';
                context.fillText('页面渲染失败', canvas.width / 2, canvas.height / 2);
            });
        }
    }

    /**
     * 添加页面标识到Canvas
     */
    addPageLabelsToCanvases(leftCanvas, rightCanvas, isOddRightEvenLeft) {
        const currentPage = this.currentPageSettingsPage || 1;
        let leftPageNum, rightPageNum;

        if (isOddRightEvenLeft) {
            rightPageNum = currentPage % 2 === 1 ? currentPage : currentPage + 1;
            leftPageNum = rightPageNum - 1;
        } else {
            leftPageNum = currentPage % 2 === 1 ? currentPage : currentPage + 1;
            rightPageNum = leftPageNum + 1;
        }

        // 确保页码有效
        leftPageNum = Math.max(1, Math.min(leftPageNum, this.pageSettingsPdfDoc?.numPages || 1));
        rightPageNum = Math.max(1, Math.min(rightPageNum, this.pageSettingsPdfDoc?.numPages || 1));

        // 左页标识
        const leftLabel = document.createElement('div');
        leftLabel.style.cssText = `
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-family: 'Microsoft YaHei', sans-serif;
            z-index: 2;
        `;
        leftLabel.textContent = `第${leftPageNum}页`;
        leftCanvas.parentElement.appendChild(leftLabel);

        // 右页标识
        const rightLabel = document.createElement('div');
        rightLabel.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-family: 'Microsoft YaHei', sans-serif;
            z-index: 2;
        `;
        rightLabel.textContent = `第${rightPageNum}页`;
        rightCanvas.parentElement.appendChild(rightLabel);
    }

    /**
     * 创建单页预览（非竖排双页模式）
     */
    createSinglePagePreview(container, canvasDataUrl, selectedEffect) {
        // 显示原始canvas
        const originalCanvas = document.getElementById('page-settings-preview-canvas');
        originalCanvas.style.display = 'block';
        originalCanvas.style.margin = '0 auto';
        originalCanvas.style.maxWidth = '60%';
        originalCanvas.style.maxHeight = '80%';

        // 应用简单的翻页效果
        setTimeout(() => {
            this.applySinglePageEffect(selectedEffect, originalCanvas);
        }, 1000);
    }

    /**
     * 创建书本页面
     */
    createBookPage(label, canvasDataUrl, pageNum, transformOrigin) {
        const page = document.createElement('div');
        page.className = 'settings-book-page';
        page.style.cssText = `
            position: relative;
            width: 50%;
            height: 100%;
            background: url('${canvasDataUrl}') no-repeat center center;
            background-size: contain;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.1);
            transform-origin: ${transformOrigin} center;
            border-right: 1px solid #ddd;
        `;

        // 添加页面标识
        const pageLabel = document.createElement('div');
        pageLabel.style.cssText = `
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-family: 'Microsoft YaHei', sans-serif;
            z-index: 2;
        `;
        pageLabel.textContent = `${label} (第${pageNum}页)`;
        page.appendChild(pageLabel);

        return page;
    }

    /**
     * 应用符合逻辑的页面翻转效果
     */
    applyLogicalPageTurn(effect, leftPage, rightPage, bookContainer, isOddRightEvenLeft) {
        switch(effect) {
            case 'turn-js':
                // 模拟从右向左翻页（符合真实书本逻辑）
                this.animateRightPageTurn(leftPage, rightPage, isOddRightEvenLeft);
                break;
            case 'fade':
                this.animateLogicalFade(leftPage, rightPage);
                break;
            case 'slide':
                this.animateLogicalSlide(leftPage, rightPage, isOddRightEvenLeft);
                break;
            case 'flip':
                this.animateLogicalFlip(leftPage, rightPage, isOddRightEvenLeft);
                break;
            case 'zoom':
                this.animateLogicalZoom(leftPage, rightPage);
                break;
            case 'wipe':
                this.animateLogicalWipe(leftPage, rightPage, isOddRightEvenLeft);
                break;
            case 'cube':
                this.animateLogicalCube(bookContainer);
                break;
            case 'page-curl':
                this.animateLogicalPageCurl(rightPage, leftPage, isOddRightEvenLeft);
                break;
            case 'accordion':
                this.animateLogicalAccordion(leftPage, rightPage);
                break;
            case 'ripple':
                this.animateLogicalRipple(leftPage, rightPage);
                break;
            default:
                this.animateRightPageTurn(leftPage, rightPage, isOddRightEvenLeft);
        }
    }

    /**
     * 模拟真实的右页翻页效果
     */
    animateRightPageTurn(leftPage, rightPage, isOddRightEvenLeft) {
        // 右页翻转效果
        rightPage.style.transition = 'transform 2s ease-in-out';
        rightPage.style.transformOrigin = 'left center';

        setTimeout(() => {
            rightPage.style.transform = 'rotateY(-180deg)';
            rightPage.style.boxShadow = '-10px 0 30px rgba(0,0,0,0.3)';
        }, 100);

        // 翻转完成后恢复
        setTimeout(() => {
            rightPage.style.transform = 'rotateY(0deg)';
            rightPage.style.boxShadow = 'inset 0 0 20px rgba(0,0,0,0.1)';
        }, 2500);
    }

    /**
     * 逻辑性的淡入淡出效果
     */
    animateLogicalFade(leftPage, rightPage) {
        // 先淡出当前页面
        [leftPage, rightPage].forEach(page => {
            page.style.transition = 'opacity 1s ease-in-out';
        });

        setTimeout(() => {
            leftPage.style.opacity = '0.3';
            rightPage.style.opacity = '0.3';
        }, 200);

        // 然后淡入新页面
        setTimeout(() => {
            leftPage.style.opacity = '1';
            rightPage.style.opacity = '1';
        }, 1500);
    }

    /**
     * 逻辑性的滑动效果
     */
    animateLogicalSlide(leftPage, rightPage, isOddRightEvenLeft) {
        // 从右向左滑动
        leftPage.style.transition = 'transform 1.5s ease-in-out';
        rightPage.style.transition = 'transform 1.5s ease-in-out';

        setTimeout(() => {
            leftPage.style.transform = 'translateX(-100%)';
            rightPage.style.transform = 'translateX(-100%)';
        }, 200);

        // 滑动完成后恢复
        setTimeout(() => {
            leftPage.style.transform = 'translateX(0)';
            rightPage.style.transform = 'translateX(0)';
        }, 2000);
    }

    /**
     * 逻辑性的翻转效果
     */
    animateLogicalFlip(leftPage, rightPage, isOddRightEvenLeft) {
        // 整个书本水平翻转
        const bookContainer = leftPage.parentElement;
        bookContainer.style.transition = 'transform 1.8s ease-in-out';
        bookContainer.style.transformStyle = 'preserve-3d';

        setTimeout(() => {
            bookContainer.style.transform = 'rotateY(180deg)';
        }, 200);

        setTimeout(() => {
            bookContainer.style.transform = 'rotateY(0deg)';
        }, 2300);
    }

    /**
     * 逻辑性的缩放效果
     */
    animateLogicalZoom(leftPage, rightPage) {
        [leftPage, rightPage].forEach(page => {
            page.style.transition = 'transform 1.5s ease-in-out';
        });

        setTimeout(() => {
            leftPage.style.transform = 'scale(0.8)';
            rightPage.style.transform = 'scale(0.8)';
        }, 200);

        setTimeout(() => {
            leftPage.style.transform = 'scale(1)';
            rightPage.style.transform = 'scale(1)';
        }, 2000);
    }

    /**
     * 逻辑性的擦除效果
     */
    animateLogicalWipe(leftPage, rightPage, isOddRightEvenLeft) {
        // 从右向左擦除
        [leftPage, rightPage].forEach(page => {
            page.style.transition = 'clip-path 1.5s ease-in-out';
            page.style.clipPath = 'inset(0 0 0 0)';
        });

        setTimeout(() => {
            rightPage.style.clipPath = 'inset(0 100% 0 0)';
            setTimeout(() => {
                leftPage.style.clipPath = 'inset(0 100% 0 0)';
            }, 200);
        }, 200);

        // 恢复
        setTimeout(() => {
            [leftPage, rightPage].forEach(page => {
                page.style.clipPath = 'inset(0 0 0 0)';
            });
        }, 2200);
    }

    /**
     * 逻辑性的立方体效果
     */
    animateLogicalCube(bookContainer) {
        bookContainer.style.transition = 'transform 2s ease-in-out';
        bookContainer.style.transformStyle = 'preserve-3d';

        setTimeout(() => {
            bookContainer.style.transform = 'rotateY(-90deg)';
        }, 200);

        setTimeout(() => {
            bookContainer.style.transform = 'rotateY(0deg)';
        }, 2500);
    }

    /**
     * 逻辑性的卷页效果
     */
    animateLogicalPageCurl(rightPage, leftPage, isOddRightEvenLeft) {
        rightPage.style.transition = 'transform 2s ease-in-out';
        rightPage.style.transformOrigin = 'left center';

        setTimeout(() => {
            rightPage.style.transform = 'perspective(1000px) rotateY(-120deg)';
            rightPage.style.boxShadow = '-15px 0 40px rgba(0,0,0,0.4)';
        }, 200);

        setTimeout(() => {
            rightPage.style.transform = 'perspective(1000px) rotateY(0deg)';
            rightPage.style.boxShadow = 'inset 0 0 20px rgba(0,0,0,0.1)';
        }, 2500);
    }

    /**
     * 逻辑性的手风琴效果
     */
    animateLogicalAccordion(leftPage, rightPage) {
        leftPage.style.transition = 'transform 1s ease-in-out';
        rightPage.style.transition = 'transform 1s ease-in-out';

        setTimeout(() => {
            rightPage.style.transform = 'scaleX(0.1)';
            setTimeout(() => {
                leftPage.style.transform = 'scaleX(0.1)';
            }, 300);
        }, 200);

        setTimeout(() => {
            leftPage.style.transform = 'scaleX(1)';
            rightPage.style.transform = 'scaleX(1)';
        }, 2000);
    }

    /**
     * 逻辑性的波纹效果
     */
    animateLogicalRipple(leftPage, rightPage) {
        const ripple = document.createElement('div');
        ripple.style.cssText = `
            position: absolute;
            top: 50%;
            right: 0;
            width: 0;
            height: 0;
            background: radial-gradient(circle, rgba(255,255,255,0.8) 0%, transparent 70%);
            border-radius: 50%;
            transform: translate(50%, -50%);
            z-index: 10;
        `;

        rightPage.appendChild(ripple);

        setTimeout(() => {
            ripple.style.transition = 'all 1.5s ease-out';
            ripple.style.width = '1000px';
            ripple.style.height = '1000px';
            ripple.style.opacity = '0';
        }, 200);

        setTimeout(() => {
            rightPage.removeChild(ripple);
        }, 2000);
    }

    /**
     * 应用单页效果
     */
    applySinglePageEffect(effect, page) {
        page.style.transition = 'all 1.5s ease-in-out';

        switch(effect) {
            case 'flip':
                setTimeout(() => {
                    page.style.transform = 'rotateY(180deg)';
                }, 500);
                break;
            case 'zoom':
                setTimeout(() => {
                    page.style.transform = 'scale(0.5)';
                    setTimeout(() => {
                        page.style.transform = 'scale(1)';
                    }, 800);
                }, 500);
                break;
            case 'fade':
                setTimeout(() => {
                    page.style.opacity = '0.3';
                    setTimeout(() => {
                        page.style.opacity = '1';
                    }, 800);
                }, 500);
                break;
            default:
                // 默认简单的淡入淡出
                setTimeout(() => {
                    page.style.opacity = '0.5';
                    setTimeout(() => {
                        page.style.opacity = '1';
                    }, 800);
                }, 500);
        }
    }

        
    /**
     * 创建淡入淡出效果
     */
    createFadeEffect(container, canvasDataUrl) {
        container.innerHTML = '';
        
        // 创建两个页面元素
        const page1 = document.createElement('div');
        page1.style.position = 'absolute';
        page1.style.top = '0';
        page1.style.left = '0';
        page1.style.width = '100%';
        page1.style.height = '100%';
        page1.style.backgroundImage = `url(${canvasDataUrl})`;
        page1.style.backgroundSize = 'contain';
        page1.style.backgroundPosition = 'center';
        page1.style.backgroundRepeat = 'no-repeat';
        page1.style.opacity = '1';
        page1.style.transition = 'opacity 1s ease-in-out';
        
        const page2 = document.createElement('div');
        page2.style.position = 'absolute';
        page2.style.top = '0';
        page2.style.left = '0';
        page2.style.width = '100%';
        page2.style.height = '100%';
        page2.style.backgroundImage = `url(${canvasDataUrl})`;
        page2.style.backgroundSize = 'contain';
        page2.style.backgroundPosition = 'center';
        page2.style.backgroundRepeat = 'no-repeat';
        page2.style.opacity = '0';
        page2.style.transition = 'opacity 1s ease-in-out';
        
        container.appendChild(page1);
        container.appendChild(page2);
        
        // 添加点击事件来触发翻页效果
        container.addEventListener('click', () => {
            if (page1.style.opacity === '1') {
                page1.style.opacity = '0';
                page2.style.opacity = '1';
            } else {
                page1.style.opacity = '1';
                page2.style.opacity = '0';
            }
        });
        
        // 保存引用以便销毁
        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }
    
    /**
     * 创建滑动效果
     */
    createSlideEffect(container, canvasDataUrl) {
        container.innerHTML = '';
        
        // 创建两个页面元素
        const page1 = document.createElement('div');
        page1.style.position = 'absolute';
        page1.style.top = '0';
        page1.style.left = '0';
        page1.style.width = '100%';
        page1.style.height = '100%';
        page1.style.backgroundImage = `url(${canvasDataUrl})`;
        page1.style.backgroundSize = 'contain';
        page1.style.backgroundPosition = 'center';
        page1.style.backgroundRepeat = 'no-repeat';
        page1.style.transform = 'translateX(0)';
        page1.style.transition = 'transform 1s ease-in-out';
        
        const page2 = document.createElement('div');
        page2.style.position = 'absolute';
        page2.style.top = '0';
        page2.style.left = '0';
        page2.style.width = '100%';
        page2.style.height = '100%';
        page2.style.backgroundImage = `url(${canvasDataUrl})`;
        page2.style.backgroundSize = 'contain';
        page2.style.backgroundPosition = 'center';
        page2.style.backgroundRepeat = 'no-repeat';
        page2.style.transform = 'translateX(100%)';
        page2.style.transition = 'transform 1s ease-in-out';
        
        container.appendChild(page1);
        container.appendChild(page2);
        
        // 添加点击事件来触发翻页效果
        container.addEventListener('click', () => {
            if (page1.style.transform === 'translateX(0px)') {
                page1.style.transform = 'translateX(-100%)';
                page2.style.transform = 'translateX(0)';
            } else {
                page1.style.transform = 'translateX(0)';
                page2.style.transform = 'translateX(100%)';
            }
        });
        
        // 保存引用以便销毁
        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }
    
    /**
     * 创建翻转效果
     */
    createFlipEffect(container, canvasDataUrl) {
        container.innerHTML = '';
        
        // 创建两个页面元素
        const page1 = document.createElement('div');
        page1.style.position = 'absolute';
        page1.style.top = '0';
        page1.style.left = '0';
        page1.style.width = '100%';
        page1.style.height = '100%';
        page1.style.backgroundImage = `url(${canvasDataUrl})`;
        page1.style.backgroundSize = 'contain';
        page1.style.backgroundPosition = 'center';
        page1.style.backgroundRepeat = 'no-repeat';
        page1.style.transform = 'rotateY(0deg)';
        page1.style.transition = 'transform 1s ease-in-out';
        page1.style.backfaceVisibility = 'hidden';
        
        const page2 = document.createElement('div');
        page2.style.position = 'absolute';
        page2.style.top = '0';
        page2.style.left = '0';
        page2.style.width = '100%';
        page2.style.height = '100%';
        page2.style.backgroundImage = `url(${canvasDataUrl})`;
        page2.style.backgroundSize = 'contain';
        page2.style.backgroundPosition = 'center';
        page2.style.backgroundRepeat = 'no-repeat';
        page2.style.transform = 'rotateY(180deg)';
        page2.style.transition = 'transform 1s ease-in-out';
        page2.style.backfaceVisibility = 'hidden';
        
        container.appendChild(page1);
        container.appendChild(page2);
        
        // 添加点击事件来触发翻页效果
        container.addEventListener('click', () => {
            if (page1.style.transform === 'rotateY(0deg)') {
                page1.style.transform = 'rotateY(-180deg)';
                page2.style.transform = 'rotateY(0deg)';
            } else {
                page1.style.transform = 'rotateY(0deg)';
                page2.style.transform = 'rotateY(180deg)';
            }
        });
        
        // 保存引用以便销毁
        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }

    /**
     * 创建缩放效果
     */
    createZoomEffect(container, canvasDataUrl) {
        container.innerHTML = '';

        const page = document.createElement('div');
        page.style.position = 'absolute';
        page.style.top = '0';
        page.style.left = '0';
        page.style.width = '100%';
        page.style.height = '100%';
        page.style.backgroundImage = `url(${canvasDataUrl})`;
        page.style.backgroundSize = 'contain';
        page.style.backgroundPosition = 'center';
        page.style.backgroundRepeat = 'no-repeat';
        page.style.transformStyle = 'preserve-3d';

        container.appendChild(page);

        container.addEventListener('click', () => {
            page.classList.remove('zoom-effect');
            void page.offsetWidth; // 触发重排
            page.classList.add('zoom-effect');
        });

        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }

    /**
     * 创建擦除效果
     */
    createWipeEffect(container, canvasDataUrl) {
        container.innerHTML = '';

        const page = document.createElement('div');
        page.style.position = 'absolute';
        page.style.top = '0';
        page.style.left = '0';
        page.style.width = '100%';
        page.style.height = '100%';
        page.style.backgroundImage = `url(${canvasDataUrl})`;
        page.style.backgroundSize = 'contain';
        page.style.backgroundPosition = 'center';
        page.style.backgroundRepeat = 'no-repeat';
        page.style.overflow = 'hidden';

        container.appendChild(page);

        container.addEventListener('click', () => {
            page.classList.remove('wipe-effect');
            void page.offsetWidth; // 触发重排
            page.classList.add('wipe-effect');
        });

        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }

    /**
     * 创建立方体翻转效果
     */
    createCubeEffect(container, canvasDataUrl) {
        container.innerHTML = '';

        const page = document.createElement('div');
        page.style.position = 'absolute';
        page.style.top = '0';
        page.style.left = '0';
        page.style.width = '100%';
        page.style.height = '100%';
        page.style.backgroundImage = `url(${canvasDataUrl})`;
        page.style.backgroundSize = 'contain';
        page.style.backgroundPosition = 'center';
        page.style.backgroundRepeat = 'no-repeat';
        page.style.transformStyle = 'preserve-3d';
        page.style.perspective = '800px';

        container.appendChild(page);

        container.addEventListener('click', () => {
            page.classList.remove('cube-effect');
            void page.offsetWidth; // 触发重排
            page.classList.add('cube-effect');
        });

        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }

    /**
     * 创建卷页效果
     */
    createPageCurlEffect(container, canvasDataUrl) {
        container.innerHTML = '';

        const page = document.createElement('div');
        page.style.position = 'absolute';
        page.style.top = '0';
        page.style.left = '0';
        page.style.width = '100%';
        page.style.height = '100%';
        page.style.backgroundImage = `url(${canvasDataUrl})`;
        page.style.backgroundSize = 'contain';
        page.style.backgroundPosition = 'center';
        page.style.backgroundRepeat = 'no-repeat';
        page.style.transformStyle = 'preserve-3d';
        page.style.perspective = '1000px';
        page.style.transformOrigin = 'right center';

        container.appendChild(page);

        container.addEventListener('click', () => {
            page.classList.remove('page-curl-effect');
            void page.offsetWidth; // 触发重排
            page.classList.add('page-curl-effect');
        });

        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }

    /**
     * 创建手风琴效果
     */
    createAccordionEffect(container, canvasDataUrl) {
        container.innerHTML = '';

        const page = document.createElement('div');
        page.style.position = 'absolute';
        page.style.top = '0';
        page.style.left = '0';
        page.style.width = '100%';
        page.style.height = '100%';
        page.style.backgroundImage = `url(${canvasDataUrl})`;
        page.style.backgroundSize = 'contain';
        page.style.backgroundPosition = 'center';
        page.style.backgroundRepeat = 'no-repeat';
        page.style.transformOrigin = 'left center';

        container.appendChild(page);

        container.addEventListener('click', () => {
            page.classList.remove('accordion-effect');
            void page.offsetWidth; // 触发重排
            page.classList.add('accordion-effect');
        });

        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }

    /**
     * 创建波纹效果
     */
    createRippleEffect(container, canvasDataUrl) {
        container.innerHTML = '';

        const page = document.createElement('div');
        page.style.position = 'absolute';
        page.style.top = '0';
        page.style.left = '0';
        page.style.width = '100%';
        page.style.height = '100%';
        page.style.backgroundImage = `url(${canvasDataUrl})`;
        page.style.backgroundSize = 'contain';
        page.style.backgroundPosition = 'center';
        page.style.backgroundRepeat = 'no-repeat';

        container.appendChild(page);

        container.addEventListener('click', () => {
            page.classList.remove('ripple-effect');
            void page.offsetWidth; // 触发重排
            page.classList.add('ripple-effect');
        });

        window.pageSettingsFlipEffect = {
            destroy: () => {
                container.removeEventListener('click', () => {});
                container.innerHTML = '';
            }
        };
    }

    // Crop Preview Methods
    /**
     * 显示裁剪预览模态框
     */
    showCropPreview() {
        // 检查是否已上传PDF文件
        if (!this.uploadedFiles || !this.uploadedFiles.pdf) {
            this.showError('请先上传PDF文件');
            return;
        }
        
        // 检查是否启用了裁剪
        if (!this.enableCrop || !this.enableCrop.checked) {
            this.showError('请先启用裁剪功能');
            return;
        }
        
        // 显示裁剪预览模态框
        const modal = new bootstrap.Modal(this.cropPreviewModal);
        modal.show();
    }
    
    /**
     * 加载PDF用于裁剪预览
     */
    async loadPdfForCropPreview() {
        try {
            // 重置当前页码
            this.currentCropPage = 1;
            
            // 获取PDF文件
            const pdfFile = this.uploadedFiles.pdf;
            if (!pdfFile) {
                this.showError('请先上传PDF文件');
                return;
            }
            
            console.log('PDF文件信息:', pdfFile);
            console.log('uploadedFiles对象:', this.uploadedFiles);
            
            // 加载PDF文档
            const pdfjsLib = window['pdfjs-dist/build/pdf'];
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.4.120/build/pdf.worker.min.js';
            
            // 使用API端点获取PDF文件
            let pdfUrl;
            if (pdfFile.url) {
                pdfUrl = pdfFile.url;
                console.log('使用PDF文件URL:', pdfUrl);
            } else {
                // 如果没有URL，构建一个
                const bookName = pdfFile.book_name || this.getCurrentBookName();
                // 对书名和文件名进行正确的URL编码
                const encodedBookName = encodeURIComponent(bookName);
                const encodedFileName = encodeURIComponent(pdfFile.name);
                pdfUrl = `/api/input-file/${encodedBookName}/${encodedFileName}`;
                console.log('构建PDF文件URL:', pdfUrl);
            }
            
            // 不需要再次编码，直接使用已编码的URL
            console.log('最终PDF URL:', pdfUrl);
            
            const loadingTask = pdfjsLib.getDocument({
                url: pdfUrl,
                cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.4.120/cmaps/',
                cMapPacked: true
            });
            
            this.cropPdfDoc = await loadingTask.promise;
            
            // 更新页面信息
            if (this.cropPdfDoc) {
                this.cropPageInfo.textContent = `第 1 页，共 ${this.cropPdfDoc.numPages} 页`;
                this.cropPageJump.value = 1;
                this.cropPageJump.max = this.cropPdfDoc.numPages;
            }
            
            // 渲染第一页
            this.renderCropPage();
        } catch (error) {
            console.error('加载PDF失败:', error);
            this.showError(`加载PDF失败: ${error.message}`);
        }
    }
    
    /**
     * 渲染裁剪预览页面
     */
    async renderCropPage() {
        if (!this.cropPdfDoc) return;
        
        try {
            // 检查是否启用了竖排双页模式
            const verticalLayout = document.getElementById('vertical-layout');
            const isVerticalLayout = verticalLayout && verticalLayout.checked;
            
            // 清除之前的渲染操作，防止"Cannot use the same canvas during multiple render() operations"错误
            const canvas = this.cropPreviewCanvas;
            const context = canvas.getContext('2d');
            context.clearRect(0, 0, canvas.width, canvas.height);
            
            // 取消正在进行的渲染操作
            if (this.currentRenderTask) {
                try {
                    this.currentRenderTask.cancel();
                } catch (e) {
                    console.log('取消渲染操作失败:', e);
                }
                this.currentRenderTask = null;
            }
            
            if (isVerticalLayout) {
                // 竖排双页模式：显示两页组合效果
                // 确保当前页是奇数页（右页）
                let rightPageNum = this.currentCropPage;
                if (rightPageNum % 2 === 0) {
                    rightPageNum = rightPageNum - 1;
                }
                
                let leftPageNum = rightPageNum + 1;
                
                // 获取页面排列顺序设置
                const isOddRightEvenLeft = this.oddRightEvenLeft.checked;
                
                // 根据页面排列顺序设置确定左右页
                let firstPageNum, secondPageNum;
                if (isOddRightEvenLeft) {
                    // 奇数页在右侧，偶数页在左边
                    firstPageNum = leftPageNum;  // 偶数页（左页）
                    secondPageNum = rightPageNum; // 奇数页（右页）
                } else {
                    // 奇数页在左边，偶数页在右边
                    firstPageNum = rightPageNum; // 奇数页（左页）
                    secondPageNum = leftPageNum;  // 偶数页（右页）
                }
                
                // 获取第一页
                const firstPage = await this.cropPdfDoc.getPage(firstPageNum);
                const firstViewport = firstPage.getViewport({ scale: 1.5 });
                
                // 准备画布 - 宽度为两页之和
                const canvas = this.cropPreviewCanvas;
                const context = canvas.getContext('2d');
                canvas.height = firstViewport.height;
                canvas.width = firstViewport.width * 2;
                
                // 清除画布内容
                context.clearRect(0, 0, canvas.width, canvas.height);
                
                // 渲染第一页（在画布的左侧）
                context.save();
                
                // 平移画布到第一页位置（在画布的左侧）
                context.translate(0, 0);
                
                const firstRenderContext = {
                    canvasContext: context,
                    viewport: firstViewport
                };
                const renderTask1 = firstPage.render(firstRenderContext);
                this.currentRenderTask = renderTask1;
                await renderTask1.promise;
                
                // 恢复画布状态
                context.restore();
                
                // 如果存在第二页，则渲染第二页（在画布的右侧）
                if (this.cropPdfDoc && secondPageNum <= this.cropPdfDoc.numPages) {
                    const secondPage = await this.cropPdfDoc.getPage(secondPageNum);
                    const secondViewport = secondPage.getViewport({ scale: 1.5 });
                    
                    context.save();
                    
                    // 平移画布到第二页位置（在画布的右侧）
                    context.translate(firstViewport.width, 0);
                    
                    const secondRenderContext = {
                        canvasContext: context,
                        viewport: secondViewport
                    };
                    const renderTask2 = secondPage.render(secondRenderContext);
                    // 不覆盖currentRenderTask，保持对第一个任务的引用
                    await renderTask2.promise;
                    
                    // 恢复画布状态
                    context.restore();
                }
                
                // 重置currentRenderTask
                this.currentRenderTask = null;
                
                // 更新原始尺寸信息
                this.cropOriginalSize.textContent = `${Math.round(canvas.width)} × ${Math.round(canvas.height)} 像素`;
                
                // 如果启用了裁剪，应用裁剪效果
                if (this.enableCrop && this.enableCrop.checked) {
                    // 获取第一页裁剪设置
                    let firstCropSettings;
                    if (isOddRightEvenLeft) {
                        // 第一页是偶数页（左页）
                        firstCropSettings = {
                            top: parseInt(this.evenTopCrop.value) || 0,
                            bottom: parseInt(this.evenBottomCrop.value) || 0,
                            left: parseInt(this.evenLeftCrop.value) || 0,
                            right: parseInt(this.evenRightCrop.value) || 0
                        };
                    } else {
                        // 第一页是奇数页（左页）
                        firstCropSettings = {
                            top: parseInt(this.oddTopCrop.value) || 0,
                            bottom: parseInt(this.oddBottomCrop.value) || 0,
                            left: parseInt(this.oddLeftCrop.value) || 0,
                            right: parseInt(this.oddRightCrop.value) || 0
                        };
                    }
                    
                    // 获取第二页裁剪设置
                    let secondCropSettings = null;
                    if (this.cropPdfDoc && secondPageNum <= this.cropPdfDoc.numPages) {
                        if (isOddRightEvenLeft) {
                            // 第二页是奇数页（右页）
                            secondCropSettings = {
                                top: parseInt(this.oddTopCrop.value) || 0,
                                bottom: parseInt(this.oddBottomCrop.value) || 0,
                                left: parseInt(this.oddLeftCrop.value) || 0,
                                right: parseInt(this.oddRightCrop.value) || 0
                            };
                        } else {
                            // 第二页是偶数页（右页）
                            secondCropSettings = {
                                top: parseInt(this.evenTopCrop.value) || 0,
                                bottom: parseInt(this.evenBottomCrop.value) || 0,
                                left: parseInt(this.evenLeftCrop.value) || 0,
                                right: parseInt(this.evenRightCrop.value) || 0
                            };
                        }
                    }
                    
                    // 创建裁剪效果的视觉指示
                    context.save();
                    
                    // 绘制半透明遮罩 - 第一页
                    context.fillStyle = 'rgba(0, 0, 0, 0.5)';
                    
                    // 第一页上方遮罩
                    context.fillRect(0, 0, firstViewport.width, firstCropSettings.top);
                    
                    // 第一页下方遮罩
                    context.fillRect(0, firstViewport.height - firstCropSettings.bottom, firstViewport.width, firstCropSettings.bottom);
                    
                    // 第一页左侧遮罩
                    context.fillRect(0, firstCropSettings.top, firstCropSettings.left, firstViewport.height - firstCropSettings.top - firstCropSettings.bottom);
                    
                    // 第一页右侧遮罩
                    context.fillRect(firstViewport.width - firstCropSettings.right, firstCropSettings.top, firstCropSettings.right, firstViewport.height - firstCropSettings.top - firstCropSettings.bottom);
                    
                    // 绘制第一页裁剪区域边框
                    const firstCroppedWidth = firstViewport.width - firstCropSettings.left - firstCropSettings.right;
                    const firstCroppedHeight = firstViewport.height - firstCropSettings.top - firstCropSettings.bottom;
                    context.strokeStyle = '#ff0000';
                    context.lineWidth = 2;
                    context.strokeRect(firstCropSettings.left, firstCropSettings.top, firstCroppedWidth, firstCroppedHeight);
                    
                    // 添加第一页裁剪尺寸标注
                    context.fillStyle = '#ff0000';
                    context.font = '14px Arial';
                    context.fillText(`${Math.round(firstCroppedWidth)} × ${Math.round(firstCroppedHeight)}`, firstCropSettings.left + 5, firstCropSettings.top + 20);
                    
                    // 如果存在第二页，绘制第二页裁剪效果
                    if (secondCropSettings) {
                        // 第二页上方遮罩
                        context.fillRect(firstViewport.width, 0, firstViewport.width, secondCropSettings.top);
                        
                        // 第二页下方遮罩
                        context.fillRect(firstViewport.width, firstViewport.height - secondCropSettings.bottom, firstViewport.width, secondCropSettings.bottom);
                        
                        // 第二页左侧遮罩
                        context.fillRect(firstViewport.width, secondCropSettings.top, secondCropSettings.left, firstViewport.height - secondCropSettings.top - secondCropSettings.bottom);
                        
                        // 第二页右侧遮罩
                        context.fillRect(firstViewport.width * 2 - secondCropSettings.right, secondCropSettings.top, secondCropSettings.right, firstViewport.height - secondCropSettings.top - secondCropSettings.bottom);
                        
                        // 绘制第二页裁剪区域边框
                        const secondCroppedWidth = firstViewport.width - secondCropSettings.left - secondCropSettings.right;
                        const secondCroppedHeight = firstViewport.height - secondCropSettings.top - secondCropSettings.bottom;
                        context.strokeRect(firstViewport.width + secondCropSettings.left, secondCropSettings.top, secondCroppedWidth, secondCroppedHeight);
                        
                        // 添加第二页裁剪尺寸标注
                        context.fillText(`${Math.round(secondCroppedWidth)} × ${Math.round(secondCroppedHeight)}`, firstViewport.width + secondCropSettings.left + 5, secondCropSettings.top + 20);
                    }
                    
                    // 计算总裁剪后尺寸
                    const totalCroppedWidth = firstCroppedWidth + (secondCropSettings ? (firstViewport.width - secondCropSettings.left - secondCropSettings.right) : 0);
                    const totalCroppedHeight = Math.max(firstCroppedHeight, secondCropSettings ? (firstViewport.height - secondCropSettings.top - secondCropSettings.bottom) : 0);
                    
                    // 更新裁剪后尺寸信息
                    this.cropCroppedSize.textContent = `${Math.round(totalCroppedWidth)} × ${Math.round(totalCroppedHeight)} 像素`;
                    
                    context.restore();
                } else {
                    // 未启用裁剪
                    this.cropCroppedSize.textContent = '未启用裁剪';
                }
                
                // 更新页面信息
                if (this.cropPdfDoc) {
                    if (secondPageNum <= this.cropPdfDoc.numPages) {
                        this.cropPageInfo.textContent = `第 ${rightPageNum}-${leftPageNum} 页，共 ${this.cropPdfDoc.numPages} 页`;
                    } else {
                        this.cropPageInfo.textContent = `第 ${rightPageNum} 页，共 ${this.cropPdfDoc.numPages} 页`;
                    }
                }
            } else {
                // 普通模式：显示单页
                // 获取当前页
                const page = await this.cropPdfDoc.getPage(this.currentCropPage);
                
                // 获取原始尺寸
                const viewport = page.getViewport({ scale: 1.5 });
                
                // 准备画布
                const canvas = this.cropPreviewCanvas;
                const context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                
                // 清除画布内容
                context.clearRect(0, 0, canvas.width, canvas.height);
                
                // 渲染原始页面
                const renderContext = {
                    canvasContext: context,
                    viewport: viewport
                };
                const renderTask = page.render(renderContext);
                this.currentRenderTask = renderTask;
                await renderTask.promise;
                this.currentRenderTask = null;
                
                // 更新原始尺寸信息
                this.cropOriginalSize.textContent = `${Math.round(viewport.width)} × ${Math.round(viewport.height)} 像素`;
                
                // 如果启用了裁剪，应用裁剪效果
                if (this.enableCrop && this.enableCrop.checked) {
                    // 获取裁剪设置
                    const isOddPage = this.currentCropPage % 2 === 1;
                    const cropSettings = isOddPage ? {
                        top: parseInt(this.oddTopCrop.value) || 0,
                        bottom: parseInt(this.oddBottomCrop.value) || 0,
                        left: parseInt(this.oddLeftCrop.value) || 0,
                        right: parseInt(this.oddRightCrop.value) || 0
                    } : {
                        top: parseInt(this.evenTopCrop.value) || 0,
                        bottom: parseInt(this.evenBottomCrop.value) || 0,
                        left: parseInt(this.evenLeftCrop.value) || 0,
                        right: parseInt(this.evenRightCrop.value) || 0
                    };
                    
                    // 计算裁剪区域
                    const cropTop = cropSettings.top;
                    const cropBottom = cropSettings.bottom;
                    const cropLeft = cropSettings.left;
                    const cropRight = cropSettings.right;
                    
                    // 确保裁剪值不超过页面尺寸
                    const maxCropTop = Math.min(cropTop, viewport.height - 10);
                    const maxCropBottom = Math.min(cropBottom, viewport.height - maxCropTop - 10);
                    const maxCropLeft = Math.min(cropLeft, viewport.width - 10);
                    const maxCropRight = Math.min(cropRight, viewport.width - maxCropLeft - 10);
                    
                    // 计算裁剪后的尺寸
                    const croppedWidth = viewport.width - maxCropLeft - maxCropRight;
                    const croppedHeight = viewport.height - maxCropTop - maxCropBottom;
                    
                    // 更新裁剪后尺寸信息
                    this.cropCroppedSize.textContent = `${Math.round(croppedWidth)} × ${Math.round(croppedHeight)} 像素`;
                    
                    // 创建裁剪效果的视觉指示
                    context.save();
                    
                    // 绘制半透明遮罩
                    context.fillStyle = 'rgba(0, 0, 0, 0.5)';
                    
                    // 上方遮罩
                    context.fillRect(0, 0, viewport.width, maxCropTop);
                    
                    // 下方遮罩
                    context.fillRect(0, viewport.height - maxCropBottom, viewport.width, maxCropBottom);
                    
                    // 左侧遮罩
                    context.fillRect(0, maxCropTop, maxCropLeft, viewport.height - maxCropTop - maxCropBottom);
                    
                    // 右侧遮罩
                    context.fillRect(viewport.width - maxCropRight, maxCropTop, maxCropRight, viewport.height - maxCropTop - maxCropBottom);
                    
                    // 绘制裁剪区域边框
                    context.strokeStyle = '#ff0000';
                    context.lineWidth = 2;
                    context.strokeRect(maxCropLeft, maxCropTop, croppedWidth, croppedHeight);
                    
                    // 添加裁剪尺寸标注
                    context.fillStyle = '#ff0000';
                    context.font = '14px Arial';
                    context.fillText(`${Math.round(croppedWidth)} × ${Math.round(croppedHeight)}`, maxCropLeft + 5, maxCropTop + 20);
                    
                    context.restore();
                } else {
                    // 未启用裁剪
                    this.cropCroppedSize.textContent = '未启用裁剪';
                }
                
                // 更新页面信息
                if (this.cropPdfDoc) {
                    this.cropPageInfo.textContent = `第 ${this.currentCropPage} 页，共 ${this.cropPdfDoc.numPages} 页`;
                }
            }
            
            this.cropPageJump.value = this.currentCropPage;
        } catch (error) {
            console.error('渲染裁剪预览页面失败:', error);
            this.showError(`渲染预览失败: ${error.message}`);
        }
    }
    
    /**
     * 显示页面设置预览模态框
     */
    showPageSettingsPreview() {
        // 检查是否已上传PDF文件
        if (!this.uploadedFiles || !this.uploadedFiles.pdf) {
            this.showError('请先上传PDF文件');
            return;
        }
        
        // 显示页面设置预览模态框
        const modal = new bootstrap.Modal(this.pageSettingsPreviewModal);
        modal.show();
        
        // 添加关闭事件监听器，确保在关闭时清理资源
        this.pageSettingsPreviewModal.addEventListener('hidden.bs.modal', () => {
            this.closePageSettingsPreview();
        }, { once: true });
    }
    
    /**
     * 关闭页面设置预览
     */
    closePageSettingsPreview() {
        // 清理翻页效果
        if (window.pageSettingsFlipEffect) {
            window.pageSettingsFlipEffect.destroy();
            window.pageSettingsFlipEffect = null;
        }
        
        // 清理翻页容器
        const flipContainer = document.getElementById('page-settings-flip-container');
        if (flipContainer) {
            flipContainer.remove();
        }
        
        // 恢复原始canvas显示
        const canvas = document.getElementById('page-settings-preview-canvas');
        if (canvas) {
            canvas.style.display = 'block';
        }
        
        // 清理PDF文档
        if (window.pageSettingsPdfDoc) {
            window.pageSettingsPdfDoc = null;
        }
        
        // 清理渲染任务
        if (window.pageSettingsRenderTask) {
            try {
                window.pageSettingsRenderTask.cancel();
            } catch (e) {
                console.error('取消页面设置预览渲染任务失败:', e);
            }
            window.pageSettingsRenderTask = null;
        }
    }
    
    /**
     * 加载PDF用于页面设置预览
     */
    async loadPdfForPageSettingsPreview() {
        try {
            // 重置当前页码
            this.currentPageSettingsPage = 1;

            // 清理之前的PDF文档
            if (this.pageSettingsPdfDoc) {
                try {
                    this.pageSettingsPdfDoc.destroy();
                } catch (e) {
                    console.log('清理PDF文档时出错:', e);
                }
                this.pageSettingsPdfDoc = null;
            }

            // 清理之前的渲染任务
            if (this.currentRenderTask) {
                try {
                    this.currentRenderTask.cancel();
                } catch (e) {
                    console.log('取消渲染任务时出错:', e);
                }
                this.currentRenderTask = null;
            }

            // 获取PDF文件
            const pdfFile = this.uploadedFiles.pdf;
            if (!pdfFile) {
                this.showError('请先上传PDF文件');
                return;
            }
            
            console.log('PDF文件信息:', pdfFile);
            console.log('uploadedFiles对象:', this.uploadedFiles);
            
            // 加载PDF文档
            const pdfjsLib = window['pdfjs-dist/build/pdf'];
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.4.120/build/pdf.worker.min.js';
            
            // 使用API端点获取PDF文件
            let pdfUrl;
            if (pdfFile.url) {
                pdfUrl = pdfFile.url;
                console.log('使用PDF文件URL:', pdfUrl);
            } else {
                // 如果没有URL，构建一个
                const bookName = pdfFile.book_name || this.getCurrentBookName();
                // 对书名和文件名进行正确的URL编码
                const encodedBookName = encodeURIComponent(bookName);
                const encodedFileName = encodeURIComponent(pdfFile.name);
                pdfUrl = `/api/input-file/${encodedBookName}/${encodedFileName}`;
                console.log('构建PDF文件URL:', pdfUrl);
            }
            
            // 不需要再次编码，直接使用已编码的URL
            console.log('最终PDF URL:', pdfUrl);
            
            const loadingTask = pdfjsLib.getDocument({
                url: pdfUrl,
                cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.4.120/cmaps/',
                cMapPacked: true,
                // 增加超时和错误处理配置
                httpHeaders: {
                    'Accept': 'application/pdf,*/*'
                }
            });

            // 使用promise包装来处理加载错误
            this.pageSettingsPdfDoc = await new Promise((resolve, reject) => {
                loadingTask.promise.then(resolve).catch(error => {
                    console.error('PDF.js加载失败:', error);
                    reject(new Error(`PDF加载失败: ${error.message || error}`));
                });
            });
            
            // 更新页面信息
            if (this.pageSettingsPdfDoc) {
                this.pageSettingsPageInfo.textContent = `第 1 页，共 ${this.pageSettingsPdfDoc.numPages} 页`;
                this.pageSettingsPageJump.value = 1;
                this.pageSettingsPageJump.max = this.pageSettingsPdfDoc.numPages;
            }
            
            // 渲染第一页
            this.renderPageSettingsPage();
        } catch (error) {
            console.error('加载PDF失败:', error);
            this.showError(`加载PDF失败: ${error.message}`);
        }
    }
    
    /**
     * 渲染页面设置预览页面
     */
    async renderPageSettingsPage() {
        if (!this.pageSettingsPdfDoc) return;

        try {
            // 检查是否启用了竖排双页模式
            const verticalLayout = document.getElementById('vertical-layout');
            const isVerticalLayout = verticalLayout && verticalLayout.checked;

            // 获取翻页效果设置
            const transitionEffect = document.getElementById('transition-effect');
            const selectedTransition = transitionEffect ? transitionEffect.value : 'none';

            // 清除之前的渲染操作，防止"Cannot use the same canvas during multiple render() operations"错误
            const canvas = this.pageSettingsPreviewCanvas;
            const context = canvas.getContext('2d');

            // 取消任何正在进行的渲染操作
            if (this.currentRenderTask) {
                try {
                    this.currentRenderTask.cancel();
                } catch (e) {
                    console.log('取消渲染操作时出错:', e);
                }
                this.currentRenderTask = null;
            }

            // 强制等待一帧，确保之前的渲染操作完全清理
            await new Promise(resolve => setTimeout(resolve, 10));

            // 清除画布内容
            context.clearRect(0, 0, canvas.width, canvas.height);

            // 重置画布状态
            context.save();
            context.setTransform(1, 0, 0, 1, 0, 0);
            context.restore();
            
            if (isVerticalLayout) {
                // 竖排双页模式：显示两页组合效果
                // 确保当前页是奇数页（右页）
                let rightPageNum = this.currentPageSettingsPage;
                if (rightPageNum % 2 === 0) {
                    rightPageNum = rightPageNum - 1;
                }
                
                let leftPageNum = rightPageNum + 1;
                
                // 获取页面排列顺序设置
                const oddRightEvenLeft = document.getElementById('oddRightEvenLeft');
                const isOddRightEvenLeft = oddRightEvenLeft && oddRightEvenLeft.checked;
                
                // 根据页面排列顺序设置确定左右页
                let firstPageNum, secondPageNum;
                if (isOddRightEvenLeft) {
                    // 奇数页在右侧，偶数页在左边
                    firstPageNum = leftPageNum;  // 偶数页（左页）
                    secondPageNum = rightPageNum; // 奇数页（右页）
                } else {
                    // 奇数页在左边，偶数页在右边
                    firstPageNum = rightPageNum; // 奇数页（左页）
                    secondPageNum = leftPageNum;  // 偶数页（右页）
                }
                
                // 获取第一页
                const firstPage = await this.pageSettingsPdfDoc.getPage(firstPageNum);
                const firstViewport = firstPage.getViewport({ scale: 1.5 });
                
                // 准备画布 - 宽度为两页之和
                const canvas = this.pageSettingsPreviewCanvas;
                const context = canvas.getContext('2d');
                canvas.height = firstViewport.height;
                canvas.width = firstViewport.width * 2;
                
                // 清除画布内容，确保没有残留的渲染操作
                context.clearRect(0, 0, canvas.width, canvas.height);
                
                // 渲染第一页（在画布的左侧）
                context.save();
                
                // 平移画布到第一页位置（在画布的左侧）
                context.translate(0, 0);
                
                const firstRenderContext = {
                    canvasContext: context,
                    viewport: firstViewport
                };
                const renderTask1 = firstPage.render(firstRenderContext);
                this.currentRenderTask = renderTask1;
                await renderTask1.promise;
                
                // 恢复画布状态
                context.restore();
                
                // 如果存在第二页，则渲染第二页（在画布的右侧）
                if (this.pageSettingsPdfDoc && secondPageNum <= this.pageSettingsPdfDoc.numPages) {
                    const secondPage = await this.pageSettingsPdfDoc.getPage(secondPageNum);
                    const secondViewport = secondPage.getViewport({ scale: 1.5 });
                    
                    context.save();
                    
                    // 平移画布到第二页位置（在画布的右侧）
                    context.translate(firstViewport.width, 0);
                    
                    const secondRenderContext = {
                        canvasContext: context,
                        viewport: secondViewport
                    };
                    const renderTask2 = secondPage.render(secondRenderContext);
                    // 不覆盖currentRenderTask，保持对第一个任务的引用
                    await renderTask2.promise;
                    
                    // 恢复画布状态
                    context.restore();
                }
                
                // 重置currentRenderTask
                this.currentRenderTask = null;
                
                // 如果启用了裁剪，应用裁剪效果
                if (this.enableCrop && this.enableCrop.checked) {
                    // 获取第一页裁剪设置
                    let firstCropSettings;
                    if (isOddRightEvenLeft) {
                        // 第一页是偶数页（左页）
                        firstCropSettings = {
                            top: parseInt(this.evenTopCrop.value) || 0,
                            bottom: parseInt(this.evenBottomCrop.value) || 0,
                            left: parseInt(this.evenLeftCrop.value) || 0,
                            right: parseInt(this.evenRightCrop.value) || 0
                        };
                    } else {
                        // 第一页是奇数页（左页）
                        firstCropSettings = {
                            top: parseInt(this.oddTopCrop.value) || 0,
                            bottom: parseInt(this.oddBottomCrop.value) || 0,
                            left: parseInt(this.oddLeftCrop.value) || 0,
                            right: parseInt(this.oddRightCrop.value) || 0
                        };
                    }
                    
                    // 获取第二页裁剪设置
                    let secondCropSettings = null;
                    if (this.pageSettingsPdfDoc && secondPageNum <= this.pageSettingsPdfDoc.numPages) {
                        if (isOddRightEvenLeft) {
                            // 第二页是奇数页（右页）
                            secondCropSettings = {
                                top: parseInt(this.oddTopCrop.value) || 0,
                                bottom: parseInt(this.oddBottomCrop.value) || 0,
                                left: parseInt(this.oddLeftCrop.value) || 0,
                                right: parseInt(this.oddRightCrop.value) || 0
                            };
                        } else {
                            // 第二页是偶数页（右页）
                            secondCropSettings = {
                                top: parseInt(this.evenTopCrop.value) || 0,
                                bottom: parseInt(this.evenBottomCrop.value) || 0,
                                left: parseInt(this.evenLeftCrop.value) || 0,
                                right: parseInt(this.evenRightCrop.value) || 0
                            };
                        }
                    }
                    
                    // 创建裁剪效果的视觉指示
                    context.save();
                    
                    // 绘制半透明遮罩 - 第一页
                    context.fillStyle = 'rgba(0, 0, 0, 0.5)';
                    
                    // 第一页上方遮罩
                    context.fillRect(0, 0, firstViewport.width, firstCropSettings.top);
                    
                    // 第一页下方遮罩
                    context.fillRect(0, firstViewport.height - firstCropSettings.bottom, firstViewport.width, firstCropSettings.bottom);
                    
                    // 第一页左侧遮罩
                    context.fillRect(0, firstCropSettings.top, firstCropSettings.left, firstViewport.height - firstCropSettings.top - firstCropSettings.bottom);
                    
                    // 第一页右侧遮罩
                    context.fillRect(firstViewport.width - firstCropSettings.right, firstCropSettings.top, firstCropSettings.right, firstViewport.height - firstCropSettings.top - firstCropSettings.bottom);
                    
                    // 绘制第一页裁剪区域边框
                    const firstCroppedWidth = firstViewport.width - firstCropSettings.left - firstCropSettings.right;
                    const firstCroppedHeight = firstViewport.height - firstCropSettings.top - firstCropSettings.bottom;
                    context.strokeStyle = '#ff0000';
                    context.lineWidth = 2;
                    context.strokeRect(firstCropSettings.left, firstCropSettings.top, firstCroppedWidth, firstCroppedHeight);
                    
                    // 添加第一页裁剪尺寸标注
                    context.fillStyle = '#ff0000';
                    context.font = '14px Arial';
                    context.fillText(`${Math.round(firstCroppedWidth)} × ${Math.round(firstCroppedHeight)}`, firstCropSettings.left + 5, firstCropSettings.top + 20);
                    
                    // 如果存在第二页，绘制第二页裁剪效果
                    if (secondCropSettings) {
                        // 第二页上方遮罩
                        context.fillRect(firstViewport.width, 0, firstViewport.width, secondCropSettings.top);
                        
                        // 第二页下方遮罩
                        context.fillRect(firstViewport.width, firstViewport.height - secondCropSettings.bottom, firstViewport.width, secondCropSettings.bottom);
                        
                        // 第二页左侧遮罩
                        context.fillRect(firstViewport.width, secondCropSettings.top, secondCropSettings.left, firstViewport.height - secondCropSettings.top - secondCropSettings.bottom);
                        
                        // 第二页右侧遮罩
                        context.fillRect(firstViewport.width * 2 - secondCropSettings.right, secondCropSettings.top, secondCropSettings.right, firstViewport.height - secondCropSettings.top - secondCropSettings.bottom);
                        
                        // 绘制第二页裁剪区域边框
                        const secondCroppedWidth = firstViewport.width - secondCropSettings.left - secondCropSettings.right;
                        const secondCroppedHeight = firstViewport.height - secondCropSettings.top - secondCropSettings.bottom;
                        context.strokeRect(firstViewport.width + secondCropSettings.left, secondCropSettings.top, secondCroppedWidth, secondCroppedHeight);
                        
                        // 添加第二页裁剪尺寸标注
                        context.fillText(`${Math.round(secondCroppedWidth)} × ${Math.round(secondCroppedHeight)}`, firstViewport.width + secondCropSettings.left + 5, secondCropSettings.top + 20);
                    }
                    
                    context.restore();
                }
                
                // 添加翻页效果的可视化指示
                if (selectedTransition !== 'none') {
                    context.save();
                    
                    // 在两页之间添加翻页效果指示
                    const centerX = firstViewport.width;
                    const centerY = firstViewport.height / 2;
                    
                    // 绘制翻页效果指示线
                    context.strokeStyle = '#0066cc';
                    context.lineWidth = 2;
                    context.setLineDash([5, 5]);
                    context.beginPath();
                    context.moveTo(centerX, 0);
                    context.lineTo(centerX, firstViewport.height);
                    context.stroke();
                    
                    // 添加翻页效果文本
                    context.fillStyle = '#0066cc';
                    context.font = '16px Arial';
                    context.textAlign = 'center';
                    context.fillText('翻页效果', centerX, centerY - 10);
                    
                    // 添加翻页效果类型
                    context.font = '14px Arial';
                    let effectText = '书籍翻页效果';
                    context.fillText(effectText, centerX, centerY + 15);
                    
                    // 添加翻页方向指示
                    context.beginPath();
                    context.moveTo(centerX - 30, centerY + 35);
                    context.lineTo(centerX + 30, centerY + 35);
                    context.lineTo(centerX + 20, centerY + 25);
                    context.moveTo(centerX + 30, centerY + 35);
                    context.lineTo(centerX + 20, centerY + 45);
                    context.stroke();
                    
                    context.restore();
                }
                
                // 更新页面信息
                if (this.pageSettingsPdfDoc) {
                    if (secondPageNum <= this.pageSettingsPdfDoc.numPages) {
                        this.pageSettingsPageInfo.textContent = `第 ${rightPageNum}-${leftPageNum} 页，共 ${this.pageSettingsPdfDoc.numPages} 页`;
                    } else {
                        this.pageSettingsPageInfo.textContent = `第 ${rightPageNum} 页，共 ${this.pageSettingsPdfDoc.numPages} 页`;
                    }
                }
            } else {
                // 普通模式：显示单页
                // 获取当前页
                const page = await this.pageSettingsPdfDoc.getPage(this.currentPageSettingsPage);
                
                // 获取原始尺寸
                const viewport = page.getViewport({ scale: 1.5 });
                
                // 准备画布
                const canvas = this.pageSettingsPreviewCanvas;
                const context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;
                
                // 清除画布内容，确保没有残留的渲染操作
                context.clearRect(0, 0, canvas.width, canvas.height);
                
                // 渲染原始页面
                const renderContext = {
                    canvasContext: context,
                    viewport: viewport
                };
                this.currentRenderTask = page.render(renderContext);
                await this.currentRenderTask.promise;
                this.currentRenderTask = null;
                
                // 如果启用了裁剪，应用裁剪效果
                if (this.enableCrop && this.enableCrop.checked) {
                    // 获取裁剪设置
                    const isOddPage = this.currentPageSettingsPage % 2 === 1;
                    const cropSettings = isOddPage ? {
                        top: parseInt(this.oddTopCrop.value) || 0,
                        bottom: parseInt(this.oddBottomCrop.value) || 0,
                        left: parseInt(this.oddLeftCrop.value) || 0,
                        right: parseInt(this.oddRightCrop.value) || 0
                    } : {
                        top: parseInt(this.evenTopCrop.value) || 0,
                        bottom: parseInt(this.evenBottomCrop.value) || 0,
                        left: parseInt(this.evenLeftCrop.value) || 0,
                        right: parseInt(this.evenRightCrop.value) || 0
                    };
                    
                    // 计算裁剪区域
                    const cropTop = cropSettings.top;
                    const cropBottom = cropSettings.bottom;
                    const cropLeft = cropSettings.left;
                    const cropRight = cropSettings.right;
                    
                    // 确保裁剪值不超过页面尺寸
                    const maxCropTop = Math.min(cropTop, viewport.height - 10);
                    const maxCropBottom = Math.min(cropBottom, viewport.height - maxCropTop - 10);
                    const maxCropLeft = Math.min(cropLeft, viewport.width - 10);
                    const maxCropRight = Math.min(cropRight, viewport.width - maxCropLeft - 10);
                    
                    // 创建裁剪效果的视觉指示
                    context.save();
                    
                    // 绘制半透明遮罩
                    context.fillStyle = 'rgba(0, 0, 0, 0.5)';
                    
                    // 上方遮罩
                    context.fillRect(0, 0, viewport.width, maxCropTop);
                    
                    // 下方遮罩
                    context.fillRect(0, viewport.height - maxCropBottom, viewport.width, maxCropBottom);
                    
                    // 左侧遮罩
                    context.fillRect(0, maxCropTop, maxCropLeft, viewport.height - maxCropTop - maxCropBottom);
                    
                    // 右侧遮罩
                    context.fillRect(viewport.width - maxCropRight, maxCropTop, maxCropRight, viewport.height - maxCropTop - maxCropBottom);
                    
                    // 绘制裁剪区域边框
                    context.strokeStyle = '#ff0000';
                    context.lineWidth = 2;
                    context.strokeRect(maxCropLeft, maxCropTop, viewport.width - maxCropLeft - maxCropRight, viewport.height - maxCropTop - maxCropBottom);
                    
                    // 添加裁剪尺寸标注
                    context.fillStyle = '#ff0000';
                    context.font = '14px Arial';
                    context.fillText(`${Math.round(viewport.width - maxCropLeft - maxCropRight)} × ${Math.round(viewport.height - maxCropTop - maxCropBottom)}`, maxCropLeft + 5, maxCropTop + 20);
                    
                    context.restore();
                }
                
                // 添加翻页效果的可视化指示
                if (selectedTransition !== 'none') {
                    context.save();
                    
                    // 在页面右侧添加翻页效果指示
                    const centerX = viewport.width / 2;
                    const centerY = viewport.height / 2;
                    
                    // 绘制翻页效果指示框
                    context.strokeStyle = '#0066cc';
                    context.lineWidth = 2;
                    context.setLineDash([5, 5]);
                    context.strokeRect(10, 10, viewport.width - 20, viewport.height - 20);
                    
                    // 添加翻页效果文本
                    context.fillStyle = '#0066cc';
                    context.font = '16px Arial';
                    context.textAlign = 'center';
                    context.fillText('翻页效果', centerX, centerY - 10);
                    
                    // 添加翻页效果类型
                    context.font = '14px Arial';
                    let effectText = '书籍翻页效果';
                    context.fillText(effectText, centerX, centerY + 15);
                    
                    // 添加翻页方向指示
                    context.beginPath();
                    context.moveTo(centerX - 30, centerY + 35);
                    context.lineTo(centerX + 30, centerY + 35);
                    context.lineTo(centerX + 20, centerY + 25);
                    context.moveTo(centerX + 30, centerY + 35);
                    context.lineTo(centerX + 20, centerY + 45);
                    context.stroke();
                    
                    context.restore();
                }
                
                // 更新页面信息
                if (this.pageSettingsPdfDoc) {
                    this.pageSettingsPageInfo.textContent = `第 ${this.currentPageSettingsPage} 页，共 ${this.pageSettingsPdfDoc.numPages} 页`;
                }
            }
            
            this.pageSettingsPageJump.value = this.currentPageSettingsPage;
        } catch (error) {
            console.error('渲染页面设置预览失败:', error);
            this.showError(`渲染预览失败: ${error.message}`);
        }
    }
    
    // 配置文件上传区域悬浮预览
    showConfigUploadPreview() {
        if (!this.uploadedFiles.config) {
            return;
        }

        const previewDiv = document.getElementById('config-upload-hover-preview');
        const previewElement = document.getElementById('config-upload-hover-preview-element');
        
        if (!previewDiv || !previewElement) {
            return;
        }

        // 显示预览窗体
        previewDiv.style.display = 'block';
        
        // 加载配置内容
        this.loadConfigContentForUploadPreview(previewElement);
    }

    hideConfigUploadPreview() {
        const previewDiv = document.getElementById('config-upload-hover-preview');
        
        if (previewDiv) {
            // 延迟隐藏，避免鼠标移动时闪烁
            setTimeout(() => {
                previewDiv.style.display = 'none';
            }, 100);
        }
    }

    async loadConfigContentForUploadPreview(contentElement) {
        try {
            if (!this.uploadedFiles.config) {
                contentElement.textContent = '没有可预览的配置文件';
                return;
            }

            const bookName = this.getCurrentBookName();
            const filename = this.uploadedFiles.config.name || this.uploadedFiles.config.filename || 'config.json';

            console.log('加载配置预览:', bookName, filename);

            // 获取配置内容
            const response = await fetch(`/api/config-content/${bookName}/${filename}`);

            if (!response.ok) {
                contentElement.textContent = '配置内容加载失败';
                return;
            }

            // 解析为JSON
            const contentType = response.headers.get('content-type');
            let configText;

            if (contentType && contentType.includes('application/json')) {
                const configData = await response.json();
                configText = JSON.stringify(configData, null, 2);
            } else {
                configText = await response.text();
            }

            // 显示配置内容
            contentElement.textContent = configText;

        } catch (error) {
            console.error('加载配置预览失败:', error);
            contentElement.textContent = '配置预览加载失败';
        }
    }

    // ==================== DeepSeek字幕校正功能 ====================

    // 初始化字幕校验功能
    initializeSubtitleValidation() {
        const validateSubtitleBtn = document.getElementById('validate-subtitle-btn');
        const fixSubtitleBtn = document.getElementById('fix-subtitle-btn');
        
        if (validateSubtitleBtn) {
            validateSubtitleBtn.addEventListener('click', () => this.performSubtitleValidation());
        }
        
        if (fixSubtitleBtn) {
            fixSubtitleBtn.addEventListener('click', () => this.fixAndSaveSubtitle());
        }
    }
    
    // 修复并保存字幕
    async fixAndSaveSubtitle() {
        const fixBtn = document.getElementById('fix-subtitle-btn');
        const validationSection = document.getElementById('subtitle-validation-result');
        const validationMessage = document.getElementById('validation-message');
        const validationDetails = document.getElementById('validation-details');
        
        // 检查是否有字幕文件
        if (!this.uploadedFiles.subs) {
            this.showError('请先上传字幕文件');
            return;
        }
        
        // 显示加载状态
        fixBtn.disabled = true;
        fixBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>修复中...';
        
        try {
            const bookName = this.getCurrentBookName();
            const filename = this.uploadedFiles.subs.name;
            
            const response = await fetch(`/api/fix-subtitle/${encodeURIComponent(bookName)}/${encodeURIComponent(filename)}`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error('字幕修复请求失败');
            }
            
            const result = await response.json();
            
            if (result.success) {
                // 修复成功
                const alertDiv = validationSection.querySelector('.alert');
                alertDiv.className = 'alert alert-success mb-0';
                validationMessage.innerHTML = `
                    <strong><i class="bi bi-check-circle me-2"></i>修复成功</strong><br>
                    ${result.message}
                `;
                
                // 显示详细的修复信息
                let detailsHTML = '<div class="mt-2 text-success"><i class="bi bi-check2-all me-1"></i>字幕文件已保存到服务器</div>';
                
                if (result.fix_report && result.fix_report.original_validation) {
                    const originalValidation = result.fix_report.original_validation;
                    const timestamps = originalValidation.invalid_timestamps || [];
                    
                    if (timestamps.length > 0) {
                        detailsHTML += '<div class="mt-3"><strong>修复详情（前10条）：</strong><ul class="mb-0 small">';
                        timestamps.slice(0, 10).forEach((item, index) => {
                            const lineNum = item.line_number || (index + 1);
                            const original = item.original || '';
                            const fixed = item.fixed || '';
                            detailsHTML += `<li class="mb-2">
                                <strong>第 ${lineNum} 行:</strong><br>
                                <span class="text-muted">修复前: <code>${original}</code></span><br>
                                <span class="text-success">修复后: <code>${fixed}</code></span>
                            </li>`;
                        });
                        if (timestamps.length > 10) {
                            detailsHTML += `<li class="text-muted"><em>...还有 ${timestamps.length - 10} 处修复</em></li>`;
                        }
                        detailsHTML += '</ul></div>';
                    }
                }
                
                validationDetails.innerHTML = detailsHTML;
                
                // 隐藏修复按钮
                fixBtn.style.display = 'none';
                
                // 添加详细日志
                this.addLogEntry(`字幕修复成功：${result.message}`, 'success');
                if (result.fix_report && result.fix_report.original_validation) {
                    const timestamps = result.fix_report.original_validation.invalid_timestamps || [];
                    this.addLogEntry('修复详情（前5条）：', 'info');
                    timestamps.slice(0, 5).forEach((item, index) => {
                        const lineNum = item.line_number || (index + 1);
                        const original = item.original || '';
                        const fixed = item.fixed || '';
                        this.addLogEntry(`  ${index + 1}. 第 ${lineNum} 行: ${original} → ${fixed}`, 'info');
                    });
                    if (timestamps.length > 5) {
                        this.addLogEntry(`  ... 还有 ${timestamps.length - 5} 处修复`, 'info');
                    }
                }
                this.showSuccess('字幕已修复并保存');
                
                // 重新校验以确认修复结果
                setTimeout(() => {
                    this.performSubtitleValidation();
                }, 1000);
            } else {
                throw new Error(result.error || '修复失败');
            }
            
        } catch (error) {
            console.error('字幕修复失败:', error);
            const alertDiv = validationSection.querySelector('.alert');
            alertDiv.className = 'alert alert-danger mb-0';
            validationMessage.innerHTML = `
                <strong><i class="bi bi-x-circle me-2"></i>修复失败</strong><br>
                ${error.message}
            `;
            validationDetails.innerHTML = '';
            this.addLogEntry(`字幕修复失败: ${error.message}`, 'error');
            this.showError('字幕修复失败');
        } finally {
            // 恢复按钮状态
            fixBtn.disabled = false;
            fixBtn.innerHTML = '<i class="bi bi-wrench me-1"></i>修复并保存';
        }
    }
    
    // 执行字幕校验
    async performSubtitleValidation() {
        const validateBtn = document.getElementById('validate-subtitle-btn');
        const validationSection = document.getElementById('subtitle-validation-result');
        const validationMessage = document.getElementById('validation-message');
        const validationDetails = document.getElementById('validation-details');
        
        // 检查是否有字幕文件
        if (!this.uploadedFiles.subs) {
            this.showError('请先上传字幕文件');
            return;
        }
        
        // 显示加载状态
        validateBtn.disabled = true;
        validateBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>校验中...';
        
        try {
            const bookName = this.getCurrentBookName();
            const filename = this.uploadedFiles.subs.name;
            
            const response = await fetch(`/api/validate-subtitle/${encodeURIComponent(bookName)}/${encodeURIComponent(filename)}`);
            
            if (!response.ok) {
                throw new Error('字幕校验请求失败');
            }
            
            const validation = await response.json();
            
            // 显示结果区域
            validationSection.style.display = 'block';
            const alertDiv = validationSection.querySelector('.alert');
            
            const fixBtn = document.getElementById('fix-subtitle-btn');
            
            if (validation.needs_fix) {
                // 需要修复
                alertDiv.className = 'alert alert-warning mb-0';
                validationMessage.innerHTML = `
                    <strong><i class="bi bi-exclamation-triangle me-2"></i>发现格式问题</strong><br>
                    检测到 ${validation.invalid_count} 处时间轴格式不符合标准
                `;
                
                // 显示详细信息
                let detailsHTML = '<div class="mt-2"><strong>问题详情（前10条）：</strong><ul class="mb-0 small">';
                const timestamps = validation.invalid_timestamps || validation.examples || [];
                if (timestamps.length > 0) {
                    timestamps.slice(0, 10).forEach((item, index) => {
                        const lineNum = item.line_number || item.line || (index + 1);
                        const original = item.original || '';
                        const fixed = item.fixed || '';
                        detailsHTML += `<li class="mb-2">
                            <strong>第 ${lineNum} 行:</strong><br>
                            <span class="text-danger">修复前: <code>${original}</code></span><br>
                            <span class="text-success">修复后: <code>${fixed}</code></span>
                        </li>`;
                    });
                    if (timestamps.length > 10) {
                        detailsHTML += `<li class="text-muted"><em>...还有 ${timestamps.length - 10} 处问题</em></li>`;
                    }
                } else {
                    detailsHTML += '<li class="text-muted">无详细信息</li>';
                }
                detailsHTML += '</ul></div>';
                detailsHTML += '<div class="mt-3 p-2 bg-light rounded">';
                detailsHTML += '<div class="text-info mb-2"><i class="bi bi-info-circle me-1"></i><strong>修复选项：</strong></div>';
                detailsHTML += '<ul class="mb-0 small">';
                detailsHTML += '<li>点击"修复并保存"按钮立即修复字幕文件（会覆盖原文件）</li>';
                detailsHTML += '<li>或者在视频生成时自动修复（不会修改原文件）</li>';
                detailsHTML += '</ul>';
                detailsHTML += '</div>';
                validationDetails.innerHTML = detailsHTML;
                
                // 显示修复按钮
                if (fixBtn) {
                    fixBtn.style.display = 'inline-block';
                }
                
                // 添加详细日志
                this.addLogEntry(`字幕校验完成：发现 ${validation.invalid_count} 处格式问题`, 'warning');
                this.addLogEntry('问题详情（前5条）：', 'info');
                timestamps.slice(0, 5).forEach((item, index) => {
                    const lineNum = item.line_number || item.line || (index + 1);
                    const original = item.original || '';
                    const fixed = item.fixed || '';
                    this.addLogEntry(`  ${index + 1}. 第 ${lineNum} 行: ${original} → ${fixed}`, 'info');
                });
                if (timestamps.length > 5) {
                    this.addLogEntry(`  ... 还有 ${timestamps.length - 5} 处问题`, 'info');
                }
            } else {
                // 格式正确
                alertDiv.className = 'alert alert-success mb-0';
                validationMessage.innerHTML = `
                    <strong><i class="bi bi-check-circle me-2"></i>格式正确</strong><br>
                    字幕时间轴格式符合标准
                `;
                validationDetails.innerHTML = '<div class="mt-2 text-success"><i class="bi bi-check2-all me-1"></i>所有时间轴格式都符合标准（毫秒为3位数字）</div>';
                
                // 隐藏修复按钮
                if (fixBtn) {
                    fixBtn.style.display = 'none';
                }
                
                this.addLogEntry('字幕校验完成：格式正确', 'success');
            }
            
        } catch (error) {
            console.error('字幕校验失败:', error);
            validationSection.style.display = 'block';
            const alertDiv = validationSection.querySelector('.alert');
            alertDiv.className = 'alert alert-danger mb-0';
            validationMessage.innerHTML = `
                <strong><i class="bi bi-x-circle me-2"></i>校验失败</strong><br>
                ${error.message}
            `;
            validationDetails.innerHTML = '';
            this.addLogEntry(`字幕校验失败: ${error.message}`, 'error');
        } finally {
            // 恢复按钮状态
            validateBtn.disabled = false;
            validateBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i>校验字幕';
        }
    }
    
    // 初始化DeepSeek相关事件
    initializeDeepSeekEvents() {
        // 检查系统是否已配置API密钥
        fetch('/api/deepseek-config')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.config) {
                    const apiKeyInput = document.getElementById('deepseek-api-key');
                    
                    if (data.config.api_key) {
                        console.log('系统已配置DeepSeek API密钥，自动填充');
                        this.hasDeepSeekApiKey = true;
                        
                        if (apiKeyInput) {
                            // 自动填充密钥并设置为密文显示
                            apiKeyInput.value = data.config.api_key;
                            apiKeyInput.type = "password";
                            // 移除之前的提示文本，因为现在已经填充了实际值
                            apiKeyInput.placeholder = "请输入DeepSeek API密钥";
                        }
                    } else if (data.config.has_api_key) {
                        // 兼容旧逻辑（如果后端不返回key但返回has_api_key状态）
                        console.log('系统已配置DeepSeek API密钥(隐藏模式)');
                        this.hasDeepSeekApiKey = true;
                        if (apiKeyInput) {
                            apiKeyInput.placeholder = "系统已配置API密钥 (可选填以覆盖)";
                        }
                    }
                }
            })
            .catch(error => console.error('获取DeepSeek配置失败:', error));

        // API密钥显示/隐藏切换
        const toggleApiKeyBtn = document.getElementById('toggle-api-key');
        const apiKeyInput = document.getElementById('deepseek-api-key');

        if (toggleApiKeyBtn && apiKeyInput) {
            toggleApiKeyBtn.addEventListener('click', () => {
                const type = apiKeyInput.type === 'password' ? 'text' : 'password';
                apiKeyInput.type = type;
                toggleApiKeyBtn.innerHTML = type === 'password' ? '<i class="bi bi-eye"></i>' : '<i class="bi bi-eye-slash"></i>';
            });
        }

        // Streamlit风格标签页切换
        const streamlitTabs = document.querySelectorAll('.streamlit-tab');
        console.log('找到Streamlit标签页数量:', streamlitTabs.length);
        
        streamlitTabs.forEach((tab, index) => {
            console.log(`标签页 ${index}:`, tab.dataset.tab);
            tab.addEventListener('click', () => {
                console.log('标签页切换为:', tab.dataset.tab);
                
                // 移除所有标签页的active类
                streamlitTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // 更新aria-selected属性
                streamlitTabs.forEach(t => t.setAttribute('aria-selected', 'false'));
                tab.setAttribute('aria-selected', 'true');
                
                this.toggleCorrectionMethod(tab.dataset.tab);
            });
        });

        // 测试连接按钮
        const testConnectionBtn = document.getElementById('test-connection');
        if (testConnectionBtn) {
            testConnectionBtn.addEventListener('click', () => this.testDeepSeekConnection());
        }

        // 网页交互方式测试连接按钮
        const testWebConnectionBtn = document.getElementById('test-web-connection');
        if (testWebConnectionBtn) {
            testWebConnectionBtn.addEventListener('click', () => this.testWebApiConnection());
        }

        // 网页交互方式API密钥显示/隐藏切换
        const toggleWebApiKeyBtn = document.getElementById('toggle-web-api-key');
        const webApiKeyInput = document.getElementById('web-deepseek-api-key');

        if (toggleWebApiKeyBtn && webApiKeyInput) {
            toggleWebApiKeyBtn.addEventListener('click', () => {
                const type = webApiKeyInput.type === 'password' ? 'text' : 'password';
                webApiKeyInput.type = type;
                toggleWebApiKeyBtn.innerHTML = type === 'password' ? '<i class="bi bi-eye"></i>' : '<i class="bi bi-eye-slash"></i>';
            });
        }

        // 文件上传处理
        const subtitleFileUpload = document.getElementById('subtitle-file-upload');
        const originalFileUpload = document.getElementById('original-file-upload');

        if (subtitleFileUpload) {
            subtitleFileUpload.addEventListener('change', (e) => this.handleSubtitleFileUpload(e));
        }

        if (originalFileUpload) {
            originalFileUpload.addEventListener('change', (e) => this.handleOriginalFileUpload(e));
        }

        // 按钮事件
        const loadSubtitleFromUploadedBtn = document.getElementById('load-subtitle-from-uploaded');
        const loadCurrentSubtitleBtn = document.getElementById('load-current-subtitle');
        const startCorrectionBtn = document.getElementById('start-correction');
        const applyCorrectionBtn = document.getElementById('apply-correction');
        const downloadCorrectedBtn = document.getElementById('download-corrected');
        const copyCorrectedBtn = document.getElementById('copy-corrected');

        if (loadSubtitleFromUploadedBtn) {
            loadSubtitleFromUploadedBtn.addEventListener('click', () => this.loadSubtitleFromUploadedFile());
        }

        if (loadCurrentSubtitleBtn) {
            loadCurrentSubtitleBtn.addEventListener('click', () => this.loadCurrentSubtitle());
        }

        if (startCorrectionBtn) {
            startCorrectionBtn.addEventListener('click', () => this.startSubtitleCorrection());
        }

        if (applyCorrectionBtn) {
            applyCorrectionBtn.addEventListener('click', () => this.applyCorrectionResult());
        }

        if (downloadCorrectedBtn) {
            downloadCorrectedBtn.addEventListener('click', () => this.downloadCorrectedSubtitle());
        }

        if (copyCorrectedBtn) {
            copyCorrectedBtn.addEventListener('click', () => this.copyCorrectedSubtitle());
        }
    }

    // 切换校正方式
    toggleCorrectionMethod(method) {
        console.log('切换校正方式:', method);
        
        const apiConfigSection = document.getElementById('api-config-section');
        const webConfigSection = document.getElementById('web-config-section');
        const methodDescription = document.getElementById('method-description');
        const webMethodDescription = document.getElementById('web-method-description');
        
        console.log('API配置区域:', apiConfigSection);
        console.log('网页交互配置区域:', webConfigSection);

        if (method === 'api') {
            console.log('显示API配置区域，隐藏网页交互配置区域');
            if (apiConfigSection) {
                apiConfigSection.style.display = 'block';
                // 添加视觉提示
                apiConfigSection.style.border = '2px solid green';
                setTimeout(() => {
                    apiConfigSection.style.border = '';
                }, 2000);
            }
            if (webConfigSection) {
                webConfigSection.style.display = 'none';
            }
            
            // 更新方法描述
            if (methodDescription) {
                methodDescription.style.display = 'inline';
                methodDescription.innerHTML = '<i class="bi bi-info-circle me-1"></i>通过DeepSeek API直接进行字幕校正，速度快但需要API密钥 (当前: API模式)';
            }
            if (webMethodDescription) {
                webMethodDescription.style.display = 'none';
            }
        } else if (method === 'web') {
            console.log('隐藏API配置区域，显示网页交互配置区域');
            if (apiConfigSection) {
                apiConfigSection.style.display = 'none';
            }
            if (webConfigSection) {
                webConfigSection.style.display = 'block';
                // 添加视觉提示
                webConfigSection.style.border = '2px solid blue';
                setTimeout(() => {
                    webConfigSection.style.border = '';
                }, 2000);
                
                // 添加API密钥输入框的视觉提示
                const apiKeyInput = document.getElementById('web-deepseek-api-key');
                
                if (apiKeyInput) {
                    apiKeyInput.style.border = '2px solid #ff6b6b';
                    apiKeyInput.placeholder = '请输入DeepSeek API密钥（必填）';
                    // 确保输入框可见且可编辑
                    apiKeyInput.disabled = false;
                    apiKeyInput.readOnly = false;
                    setTimeout(() => {
                        apiKeyInput.style.border = '';
                    }, 5000);
                } else {
                    console.error('找不到网页交互API密钥输入框');
                }
                
                // 显示提示信息
                this.showAlert('请输入DeepSeek API密钥以使用网页交互方式', 'info');
                
                // 滚动到网页交互配置区域
                webConfigSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            
            // 更新方法描述
            if (methodDescription) {
                methodDescription.style.display = 'none';
            }
            if (webMethodDescription) {
                webMethodDescription.style.display = 'inline';
                webMethodDescription.innerHTML = '<i class="bi bi-info-circle me-1"></i>通过模拟网页操作进行字幕校正，使用API认证，适合处理复杂场景 (当前: 网页交互模式)';
            }
        }
    }

    // 测试DeepSeek连接
    async testDeepSeekConnection() {
        const testBtn = document.getElementById('test-connection');
        const statusDiv = document.getElementById('connection-status');
        const apiKey = document.getElementById('deepseek-api-key').value.trim();

        if (!apiKey && !this.hasDeepSeekApiKey) {
            this.showAlert('请输入DeepSeek API密钥', 'warning');
            return;
        }

        // 禁用按钮，显示加载状态
        testBtn.disabled = true;
        testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>测试中...';

        if (statusDiv) {
            statusDiv.innerHTML = '<span class="badge bg-warning"><i class="bi bi-arrow-repeat me-1"></i>连接测试中...</span>';
        }

        try {
            const response = await fetch('/api/deepseek-test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ api_key: apiKey })
            });

            const result = await response.json();

            if (result.success) {
                if (statusDiv) {
                    statusDiv.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>连接成功</span>';
                }
                this.showAlert('DeepSeek API连接测试成功！', 'success');
            } else {
                if (statusDiv) {
                    statusDiv.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>连接失败</span>';
                }
                this.showAlert(`连接测试失败: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('DeepSeek连接测试失败:', error);
            if (statusDiv) {
                statusDiv.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>测试失败</span>';
            }
            this.showAlert('连接测试失败，请检查网络连接', 'error');
        } finally {
            // 恢复按钮状态
            testBtn.disabled = false;
            testBtn.innerHTML = '<i class="bi bi-wifi"></i> 测试连接';
        }
    }

    // 测试网页交互API连接
    async testWebApiConnection() {
        const apiKeyElement = document.getElementById('web-deepseek-api-key');
        console.log('测试网页交互API连接 - API密钥输入框元素:', apiKeyElement);
        
        // 确保元素存在并可访问
        if (!apiKeyElement) {
            this.showAlert('找不到网页交互API密钥输入框', 'error');
            return;
        }
        
        const apiKey = apiKeyElement.value.trim();
        const testWebBtn = document.getElementById('test-web-connection');
        const webApiStatus = document.getElementById('web-connection-status');
        
        console.log('测试网页交互API连接 - API密钥:', apiKey ? '已输入(' + apiKey.length + '字符)' : '未输入');
        console.log('测试网页交互API连接 - API密钥元素值:', apiKeyElement.value);
        console.log('测试网页交互API连接 - 输入框类型:', apiKeyElement.type);
        console.log('测试网页交互API连接 - 输入框是否禁用:', apiKeyElement.disabled);
        console.log('测试网页交互API连接 - 输入框是否只读:', apiKeyElement.readOnly);
        
        if (!apiKey) {
            this.showAlert('请先输入DeepSeek API密钥', 'warning');
            // 高亮API密钥输入框
            apiKeyElement.style.border = '2px solid #ff6b6b';
            setTimeout(() => {
                apiKeyElement.style.border = '';
            }, 3000);
            return;
        }
        
        // 显示加载状态
        testWebBtn.disabled = true;
        testWebBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>测试中...';
        
        try {
            const response = await fetch('/api/deepseek-test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    api_key: apiKey
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                webApiStatus.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>连接成功</span>';
                this.showAlert('网页交互方式API连接测试成功！', 'success');
            } else {
                webApiStatus.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>连接失败</span>';
                // 优先显示data.message中的错误信息
                const errorMessage = data.data && data.data.message ? data.data.message : data.message || data.error || '未知错误';
                this.showAlert('网页交互方式API连接测试失败: ' + errorMessage, 'error');
            }
        } catch (error) {
            console.error('测试网页交互API连接失败:', error);
            webApiStatus.innerHTML = '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>测试失败</span>';
            this.showAlert('测试网页交互API连接时发生网络错误', 'error');
        } finally {
            // 恢复按钮状态
            testWebBtn.disabled = false;
            testWebBtn.innerHTML = '<i class="bi bi-wifi"></i> 测试连接';
        }
    }

    // 处理字幕文件上传
    async handleSubtitleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        try {
            const text = await this.readFileContent(file);
            document.getElementById('subtitle-text').value = text;
            this.showAlert(`字幕文件 "${file.name}" 加载成功`, 'success');
        } catch (error) {
            console.error('读取字幕文件失败:', error);
            this.showAlert('读取字幕文件失败', 'error');
        }
    }

    // 处理原文文件上传
    async handleOriginalFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        try {
            const text = await this.readFileContent(file);
            document.getElementById('original-text').value = text;
            this.showAlert(`原文文件 "${file.name}" 加载成功`, 'success');
        } catch (error) {
            console.error('读取原文文件失败:', error);
            this.showAlert('读取原文文件失败', 'error');
        }
    }

    // 读取文件内容
    readFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = reject;
            reader.readAsText(file, 'UTF-8');
        });
    }

    // 从上传文件加载字幕
    async loadSubtitleFromUploadedFile() {
        const fileInput = document.getElementById('subtitle-file-upload');
        if (!fileInput.files.length) {
            this.showAlert('请先选择字幕文件', 'warning');
            return;
        }

        const file = fileInput.files[0];
        try {
            const text = await this.readFileContent(file);
            document.getElementById('subtitle-text').value = text;
            this.showAlert('字幕文件内容已加载', 'success');
        } catch (error) {
            this.showAlert('读取字幕文件失败', 'error');
        }
    }

    // 加载当前字幕
    async loadCurrentSubtitle() {
        try {
            const bookName = this.getCurrentBookName();
            if (!bookName) {
                this.showAlert('请先选择书籍', 'warning');
                return;
            }

            // 获取当前字幕文件名
            let subtitleFilename = null;
            if (this.uploadedFiles.subs) {
                subtitleFilename = this.uploadedFiles.subs.name || this.uploadedFiles.subs.filename;
            }

            if (!subtitleFilename) {
                this.showAlert('没有找到当前字幕文件', 'warning');
                return;
            }

            const response = await fetch(`/api/subs-content/${bookName}/${subtitleFilename}`);
            if (!response.ok) {
                throw new Error('获取字幕内容失败');
            }

            const data = await response.json();
            const subtitleText = data.subtitle_content || data.content;

            if (subtitleText) {
                document.getElementById('subtitle-text').value = subtitleText;
                this.showAlert('当前字幕内容已加载', 'success');
            } else {
                this.showAlert('字幕内容为空', 'warning');
            }
        } catch (error) {
            console.error('加载当前字幕失败:', error);
            this.showAlert('加载当前字幕失败', 'error');
        }
    }

    // 开始字幕校正
    async startSubtitleCorrection() {
        // 获取选择的校正方式（Streamlit标签页）
        const activeTab = document.querySelector('.streamlit-tab.active');
        const correctionMethod = activeTab ? activeTab.dataset.tab : 'api';
        
        // 获取输入内容
        const subtitleText = document.getElementById('subtitle-text').value.trim();
        const originalText = document.getElementById('original-text').value.trim();
        const bookName = this.getCurrentBookName();

        // 验证输入
        if (!subtitleText) {
            this.showAlert('请输入字幕文本', 'warning');
            return;
        }

        if (!originalText) {
            this.showAlert('请输入原文文本', 'warning');
            return;
        }

        // 根据校正方式验证不同的参数
        let requestParams = {
            subtitle_text: subtitleText,
            original_text: originalText,
            book_name: bookName
        };

        if (correctionMethod === 'api') {
            const apiKey = document.getElementById('deepseek-api-key').value.trim();
            const enableDeepthink = document.getElementById('enable-deepthink').checked;
            const batchSize = parseInt(document.getElementById('batch-size').value) || 100;
            
            if (!apiKey && !this.hasDeepSeekApiKey) {
                this.showAlert('请输入DeepSeek API密钥', 'warning');
                return;
            }
            
            if (apiKey) {
                requestParams.api_key = apiKey;
            }
            requestParams.enable_deepthink = enableDeepthink;
            requestParams.batch_size = batchSize;
        } else if (correctionMethod === 'web') {
            const apiKeyElement = document.getElementById('web-deepseek-api-key');
            console.log('网页交互API密钥输入框元素:', apiKeyElement);
            
            // 确保元素存在并可访问
            if (!apiKeyElement) {
                this.showAlert('找不到网页交互API密钥输入框', 'error');
                return;
            }
            
            let apiKey = apiKeyElement.value.trim();
            
            // 如果网页交互方式的API密钥为空，尝试从API方式的输入框获取
            if (!apiKey) {
                const apiModeKeyElement = document.getElementById('deepseek-api-key');
                if (apiModeKeyElement) {
                    apiKey = apiModeKeyElement.value.trim();
                    console.log('网页交互方式的API密钥为空，从API方式输入框获取:', apiKey ? '成功(' + apiKey.length + '字符)' : '失败');
                    
                    if (apiKey) {
                        // 自动填充到网页交互方式的输入框
                        apiKeyElement.value = apiKey;
                        this.showAlert('已自动使用API方式的密钥', 'info');
                    }
                }
            }
            
            const headlessMode = document.getElementById('headless-mode').checked;
            const enableDeepthink = document.getElementById('web-enable-deepthink').checked;
            
            console.log('DeepSeek网页交互方式 - API密钥:', apiKey ? '已输入(' + apiKey.length + '字符)' : '未输入');
            console.log('DeepSeek网页交互方式 - API密钥元素值:', apiKeyElement.value);
            console.log('DeepSeek网页交互方式 - 输入框类型:', apiKeyElement.type);
            console.log('DeepSeek网页交互方式 - 输入框是否禁用:', apiKeyElement.disabled);
            console.log('DeepSeek网页交互方式 - 输入框是否只读:', apiKeyElement.readOnly);
            
            if (!apiKey) {
                this.showAlert('请输入DeepSeek API密钥（在API配置区域或网页交互配置区域）', 'warning');
                // 高亮API密钥输入框
                apiKeyElement.style.border = '2px solid #ff6b6b';
                setTimeout(() => {
                    apiKeyElement.style.border = '';
                }, 3000);
                return;
            }
            
            requestParams.api_key = apiKey;
            requestParams.headless = headlessMode;
            requestParams.enable_deepthink = enableDeepthink;
            requestParams.use_web_mode = true;  // 【关键】明确告诉后端使用网页交互模式
            
            // 添加调试日志
            console.log('网页交互方式 - 请求参数:', JSON.stringify(requestParams, null, 2));
            
            // 强制显示API密钥状态（用于调试）
            alert(`[调试] 网页交互方式\nAPI密钥: ${requestParams.api_key ? '已设置(' + requestParams.api_key.length + '字符)' : '未设置'}\n请求参数: ${JSON.stringify(requestParams, null, 2)}`);
        }

        // 禁用按钮，显示进度
        const startBtn = document.getElementById('start-correction');
        startBtn.disabled = true;
        startBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>校正中...';

        try {
            console.log(`开始DeepSeek字幕校正 (${correctionMethod}方式)...`);

            // 根据校正方式选择不同的API端点
            const endpoint = correctionMethod === 'api' 
                ? '/api/deepseek-correct-subtitle' 
                : '/api/deepseek-correct-subtitle-web';

            // 添加请求调试日志
            console.log(`发送请求到: ${endpoint}`);
            console.log('请求体:', JSON.stringify(requestParams, null, 2));
            
            // 特别检查API密钥
            if (correctionMethod === 'web') {
                console.log('[WEB DEBUG] 网页交互方式发送请求前的API密钥检查:');
                console.log('[WEB DEBUG] requestParams.api_key:', requestParams.api_key ? '存在(' + requestParams.api_key.length + '字符)' : '不存在');
                console.log('[WEB DEBUG] requestParams.api:', requestParams.api ? '存在(' + requestParams.api.length + '字符)' : '不存在');
                console.log('[WEB DEBUG] 完整的requestParams:', JSON.stringify(requestParams, null, 2));
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestParams)
            });

            const result = await response.json();

            if (result.success) {
                this.showCorrectionResult(result);
                this.showAlert('字幕校正完成！', 'success');
                console.log('字幕校正成功:', result);
            } else {
                // 确保错误信息是字符串而不是对象
                let errorMessage = result.error;
                if (typeof errorMessage === 'object') {
                    errorMessage = JSON.stringify(errorMessage);
                }
                this.showAlert(`字幕校正失败: ${errorMessage}`, 'error');
                console.error('字幕校正失败:', result);
            }
        } catch (error) {
            console.error('字幕校正请求失败:', error);
            this.showAlert('字幕校正请求失败，请检查网络连接', 'error');
        } finally {
            // 恢复按钮状态
            startBtn.disabled = false;
            startBtn.innerHTML = '<i class="bi bi-magic"></i> 开始字幕校正';
        }
    }

    // 显示校正结果
    showCorrectionResult(result) {
        const resultsDiv = document.getElementById('correction-results');
        const originalDisplay = document.getElementById('original-subtitle-display');
        const correctedDisplay = document.getElementById('corrected-subtitle-display');
        const processingTime = document.getElementById('processing-time');

        if (resultsDiv) {
            resultsDiv.style.display = 'block';
        }

        if (originalDisplay) {
            originalDisplay.value = result.original_subtitle || '';
        }

        if (correctedDisplay) {
            correctedDisplay.value = result.corrected_subtitle || '';
        }

        if (processingTime) {
            processingTime.textContent = `处理时间：${(result.processing_time || 0).toFixed(2)}秒`;
        }

        // 保存校正结果供后续使用
        this.lastCorrectionResult = result;
        
        // 自动生成智能文件名
        const filenameInput = document.getElementById('corrected-filename');
        if (filenameInput) {
            const bookName = this.getCurrentBookName() || '字幕';
            const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            const suggestedFilename = `${bookName}_校正_${timestamp}.srt`;
            filenameInput.value = suggestedFilename;
        }

        // 滚动到结果区域
        if (resultsDiv) {
            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // 应用校正结果
    async applyCorrectionResult() {
        if (!this.lastCorrectionResult || !this.lastCorrectionResult.corrected_subtitle) {
            this.showAlert('没有可应用的校正结果', 'warning');
            return;
        }

        const correctedSubtitle = this.lastCorrectionResult.corrected_subtitle;

        try {
            // 尝试将校正后的字幕保存为当前字幕
            const bookName = this.getCurrentBookName();
            if (bookName) {
                // 创建新的字幕文件名
                const filename = `corrected_${Date.now()}.srt`;

                // 这里可以调用API保存校正后的字幕到内存
                // 当前只是将内容填充到字幕文本框
                document.getElementById('subtitle-text').value = correctedSubtitle;
                this.showAlert('校正结果已应用，您可以在后续步骤中使用', 'success');
            } else {
                this.showAlert('请先选择书籍', 'warning');
            }
        } catch (error) {
            console.error('应用校正结果失败:', error);
            this.showAlert('应用校正结果失败', 'error');
        }
    }

    // 下载校正后的字幕
    downloadCorrectedSubtitle() {
        if (!this.lastCorrectionResult || !this.lastCorrectionResult.corrected_subtitle) {
            this.showAlert('没有可下载的校正结果', 'warning');
            return;
        }

        const correctedSubtitle = this.lastCorrectionResult.corrected_subtitle;
        
        // 获取用户输入的文件名
        const filenameInput = document.getElementById('corrected-filename');
        let filename = filenameInput ? filenameInput.value.trim() : '';
        
        // 如果用户没有输入文件名，使用默认值
        if (!filename) {
            filename = `subtitle_corrected_${Date.now()}.srt`;
        } else {
            // 确保文件名有.srt扩展名
            if (!filename.toLowerCase().endsWith('.srt')) {
                filename += '.srt';
            }
        }

        // 创建下载链接
        const blob = new Blob([correctedSubtitle], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        this.showAlert(`字幕文件 "${filename}" 已下载`, 'success');
    }

    // 复制校正后的字幕到剪贴板
    async copyCorrectedSubtitle() {
        if (!this.lastCorrectionResult || !this.lastCorrectionResult.corrected_subtitle) {
            this.showAlert('没有可复制的校正结果', 'warning');
            return;
        }

        const correctedSubtitle = this.lastCorrectionResult.corrected_subtitle;

        try {
            await navigator.clipboard.writeText(correctedSubtitle);
            this.showAlert('校正结果已复制到剪贴板', 'success');
        } catch (error) {
            console.error('复制到剪贴板失败:', error);

            // 降级方案：使用传统的复制方法
            const textarea = document.createElement('textarea');
            textarea.value = correctedSubtitle;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);

            this.showAlert('校正结果已复制到剪贴板', 'success');
        }
    }

    // 显示提示信息
    showAlert(message, type = 'info') {
        // 创建提示元素
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        // 自动消失
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 5000);
    }
    

    

    













    

    





  // 验证字幕格式
    async validateSubtitleFormat(bookName, filename) {
        try {
            // 简化日志输出，只在有问题时才显示
            const response = await fetch(`/api/validate-subtitle/${encodeURIComponent(bookName)}/${encodeURIComponent(filename)}`);

            if (!response.ok) {
                return; // 静默失败，不影响用户体验
            }

            const validation = await response.json();

            if (validation.needs_fix && validation.invalid_count > 0) {
                // 只在有问题时显示简洁的提示
                const message = `检测到字幕格式问题 (${validation.invalid_count}处)，视频生成时将自动修复`;
                this.addLogEntry(message, 'info');
                // 不显示alert，避免打扰用户
            }

        } catch (error) {
            // 静默处理错误，不影响界面
            console.log('字幕格式验证跳过:', error.message);
        }
    }

}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const app = new VideoCreatorApp();
    
    // 确保网页交互方式API密钥输入框在页面加载时可用
    setTimeout(() => {
        const webApiKeyInput = document.getElementById('web-deepseek-api-key');
        if (webApiKeyInput) {
            console.log('网页交互API密钥输入框已找到，确保可用状态');
            webApiKeyInput.disabled = false;
            webApiKeyInput.readOnly = false;
        } else {
            console.error('网页交互API密钥输入框未找到');
        }
    }, 1000);
    
    // 添加折叠/展开功能的事件监听器
    document.querySelectorAll('.collapse-toggle').forEach(toggle => {
        toggle.addEventListener('click', function() {
            const targetId = this.getAttribute('data-bs-target');
            const target = document.querySelector(targetId);
            const icon = this.querySelector('.collapse-icon');
            
            if (target) {
                // 切换折叠状态
                if (target.classList.contains('show')) {
                    target.classList.remove('show');
                    icon.style.transform = 'rotate(0deg)';
                } else {
                    target.classList.add('show');
                    icon.style.transform = 'rotate(90deg)';
                }
            }
        });
    });
});
