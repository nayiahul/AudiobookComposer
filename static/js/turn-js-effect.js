// Turn.js翻页效果实现

// 使用统一的日志过滤机制，不重复重写console.log
// 如果app.js已经重写了console.log，则不再重写
if (typeof console.logFilter !== 'function') {
    // 只在app.js未设置日志过滤时才设置
    const originalConsoleLogTurn = console.log;
    console.log = function(...args) {
        // 只允许错误级别的日志输出
        if (args.length > 0 && typeof args[0] === 'string' && args[0].includes('错误')) {
            originalConsoleLogTurn.apply(console, args);
        }
    };
}

class TurnJsPageEffect {
    constructor(canvasOrId) {
        if (typeof canvasOrId === 'string') {
            // 如果传入的是ID
            this.canvasId = canvasOrId;
            this.canvas = document.getElementById(canvasOrId);
        } else if (canvasOrId instanceof HTMLElement) {
            // 如果传入的是DOM元素
            this.canvas = canvasOrId;
            this.canvasId = canvasOrId.id;
        } else {
            throw new Error('TurnJsPageEffect构造函数需要传入canvas元素ID或canvas元素');
        }
        
        this.isInitialized = false;
        this.turnJsLoaded = false;
    }

    // 初始化Turn.js翻页效果
    async init() {
        if (this.isInitialized) return;

        try {
            // 动态加载jQuery和Turn.js
            await this.loadScripts();
            
            // 创建Turn.js所需的HTML结构
            this.createTurnJsStructure();
            
            // 初始化Turn.js
            this.initTurnJs();
            
            this.isInitialized = true;
        } catch (error) {
            console.error('初始化Turn.js翻页效果失败:', error);
        }
    }

    // 动态加载jQuery和Turn.js
    async loadScripts() {
        return new Promise((resolve, reject) => {
            // 检查是否已加载jQuery
            if (typeof jQuery === 'undefined') {
                const jqueryScript = document.createElement('script');
                jqueryScript.src = 'https://code.jquery.com/jquery-3.6.0.min.js';
                jqueryScript.onload = () => {
                    this.loadTurnJs(resolve, reject);
                };
                jqueryScript.onerror = () => reject(new Error('加载jQuery失败'));
                document.head.appendChild(jqueryScript);
            } else {
                this.loadTurnJs(resolve, reject);
            }
        });
    }

    // 加载Turn.js
    loadTurnJs(resolve, reject) {
        if (typeof $.fn.turn === 'undefined') {
            const turnScript = document.createElement('script');
            turnScript.src = 'https://cdn.jsdelivr.net/npm/turn.js@4.1.0/turn.min.js';
            turnScript.onload = () => {
                this.turnJsLoaded = true;
                resolve();
            };
            turnScript.onerror = () => reject(new Error('加载Turn.js失败'));
            document.head.appendChild(turnScript);
        } else {
            this.turnJsLoaded = true;
            resolve();
        }
    }

    // 创建Turn.js所需的HTML结构
    createTurnJsStructure() {
        // 保存原始画布内容
        let originalContent = "";
        
        if (this.canvas && this.canvas.tagName === 'CANVAS') {
            // 如果是画布元素，创建一个示例文本内容
            originalContent = "这是一个PDF页面的示例文本，用于演示Turn.js翻页效果。Turn.js是一个JavaScript库，可以创建类似真实书籍的翻页效果。它支持触摸事件，可以在移动设备上使用。用户可以通过滑动或点击来翻页，就像翻阅真实的书籍一样。";
            
            // 保存原始画布样式
            const canvasStyle = window.getComputedStyle(this.canvas);
            const canvasWidth = this.canvas.width;
            const canvasHeight = this.canvas.height;
            
            // 隐藏原始画布
            this.canvas.style.display = 'none';
            
            // 创建Turn.js结构，并设置与画布相同的尺寸
            this.canvas.insertAdjacentHTML('afterend', `
                <div id="turn-js-magazine" style="width: ${canvasWidth}px; height: ${canvasHeight}px;">
                    <div id="turn-js-pages" style="width: 100%; height: 100%;"></div>
                    <div id="turn-js-content" style="height: 0; overflow: hidden; width: 100%;">
                        <div id="turn-js-content-text" style="width: 100%; white-space: pre-wrap; box-sizing: border-box; padding: 0 10px;">${originalContent}</div>
                    </div>
                </div>
                <div id="turn-js-alert" style="position: absolute; bottom: 40px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.6); border-radius: 4px; color: #fff; z-index: 10; font-size: 12px; padding: 6px 10px; display: none;"></div>
            `);
        } else {
            // 如果不是画布元素，使用原始HTML内容
            originalContent = this.canvas.innerHTML;
            
            // 创建Turn.js结构
            this.canvas.innerHTML = `
                <div id="turn-js-magazine">
                    <div id="turn-js-pages"></div>
                    <div id="turn-js-content">
                        <div id="turn-js-content-text">${originalContent}</div>
                    </div>
                </div>
                <div id="turn-js-alert"></div>
            `;
        }
    }

    // 初始化Turn.js
    initTurnJs() {
        if (!this.turnJsLoaded) return;

        // 获取magazine元素
        let magazine;
        if (this.canvas && this.canvas.tagName === 'CANVAS') {
            // 如果是画布元素，magazine元素是插入到画布后面的元素
            magazine = document.getElementById('turn-js-magazine');
        } else {
            // 如果不是画布元素，magazine元素是canvas的子元素
            magazine = this.canvas.querySelector('#turn-js-magazine');
        }
        
        if (!magazine) {
            console.error('Turn.js magazine element not found');
            return;
        }
        
        const $wrap = $(magazine);
        const $page = $("#turn-js-pages");
        const w = $page.width();
        const h = $page.height();
        const $content = $("#turn-js-content-text");
        
        // 获取画布内容作为示例文本
        let writeStr;
        if (this.canvas && this.canvas.tagName === 'CANVAS') {
            // 如果是画布元素，创建一个示例文本
            writeStr = "这是一个PDF页面的示例文本，用于演示Turn.js翻页效果。Turn.js是一个JavaScript库，可以创建类似真实书籍的翻页效果。它支持触摸事件，可以在移动设备上使用。用户可以通过滑动或点击来翻页，就像翻阅真实的书籍一样。";
            
            // 尝试获取画布上的图像数据
            try {
                const ctx = this.canvas.getContext('2d');
                const imageData = ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
                // 这里可以将图像数据转换为文本，但为了简单起见，我们使用示例文本
            } catch (e) {
                console.log('错误: 无法获取画布图像数据，使用示例文本');
            }
        } else {
            // 如果不是画布元素，使用HTML内容
            writeStr = $content.html() || "这是一个示例文本，用于演示Turn.js翻页效果。Turn.js是一个JavaScript库，可以创建类似真实书籍的翻页效果。它支持触摸事件，可以在移动设备上使用。用户可以通过滑动或点击来翻页，就像翻阅真实的书籍一样。";
        }
        
        $content.html(writeStr);
        const len = writeStr.length;
        $content.css('height', 'auto');
        const cH = $content.height();
        let pageStrNum;
        
        // 设置内容区域高度与页面高度一致
        $content.css('height', h + 'px');
        
        if (cH > h) {
            pageStrNum = (h / cH) * len;
            let obj = this.overflowhiddenTow($content, writeStr, h);
            $page.append('<div class="turn-page">' + obj.curr + '</div>');
            
            while (obj.next && obj.next.length > 0) {
                obj = this.overflowhiddenTow($content, obj.next, h);
                $page.append('<div class="turn-page">' + obj.curr + '</div>');
            }
        } else {
            $page.append('<div class="turn-page">' + writeStr + '</div>');
        }
        
        // 初始化Turn.js
        try {
            $wrap.turn({
                width: w,
                height: h,
                elevation: 50,
                display: 'double',
                gradients: true,
                acceleration: true,
                autoCenter: true,
                when: {
                    turning: (e, page, view) => {
                        // 翻页时显示提示
                        const alert = document.getElementById('turn-js-alert');
                        if (alert) {
                            alert.textContent = `正在翻到第 ${page} 页...`;
                            alert.style.display = 'block';
                            
                            // 2秒后隐藏提示
                            setTimeout(() => {
                                alert.style.display = 'none';
                            }, 2000);
                        }
                    },
                    turned: (e, page) => {
                        // 翻页完成后更新提示
                        const alert = document.getElementById('turn-js-alert');
                        if (alert) {
                            alert.textContent = `当前是第 ${page} 页`;
                            alert.style.display = 'block';
                            
                            // 2秒后隐藏提示
                            setTimeout(() => {
                                alert.style.display = 'none';
                            }, 2000);
                        }
                    }
                }
            });
            
            // 添加触摸和鼠标事件
            this.addTouchEvents(magazine);
            
            console.log('错误: Turn.js initialized successfully');
        } catch (error) {
            console.error('Error initializing Turn.js:', error);
            
            // 显示错误提示
            const alert = document.getElementById('turn-js-alert');
            if (alert) {
                alert.textContent = 'Turn.js初始化失败，请检查控制台获取详细信息';
                alert.style.display = 'block';
            }
        }
    }

    // 文字切割算法
    overflowhiddenTow($texts, str, at) {
        const pageStrNum = (at / $texts.parent().height()) * str.length;
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

    // 添加触摸和鼠标事件处理
    addTouchEvents(magazine) {
        // 使用jQuery对象
        const $magazine = $(magazine);
        
        // 触摸事件处理
        $magazine.on('touchstart', function(e) {
            const touch = e.originalEvent.touches[0];
            const startX = touch.pageX;
            const width = $magazine.width();
            
            $magazine.on('touchmove', function(e) {
                e.preventDefault();
            });
            
            $magazine.on('touchend', function(e) {
                const touch = e.originalEvent.changedTouches[0];
                const endX = touch.pageX;
                const diffX = endX - startX;
                
                // 判断滑动方向
                if (Math.abs(diffX) > 50) { // 最小滑动距离
                    if (diffX > 0) {
                        // 向右滑动，向前翻页
                        $magazine.turn('previous');
                    } else {
                        // 向左滑动，向后翻页
                        $magazine.turn('next');
                    }
                }
                
                // 移除事件监听
                $magazine.off('touchmove touchend');
            });
        });
        
        // 鼠标事件处理
        $magazine.on('mousedown', function(e) {
            const startX = e.pageX;
            const width = $magazine.width();
            
            $magazine.on('mousemove', function(e) {
                e.preventDefault();
            });
            
            $magazine.on('mouseup', function(e) {
                const endX = e.pageX;
                const diffX = endX - startX;
                
                // 判断滑动方向
                if (Math.abs(diffX) > 50) { // 最小滑动距离
                    if (diffX > 0) {
                        // 向右滑动，向前翻页
                        $magazine.turn('previous');
                    } else {
                        // 向左滑动，向后翻页
                        $magazine.turn('next');
                    }
                }
                
                // 移除事件监听
                $magazine.off('mousemove mouseup');
            });
        });
        
        // 添加键盘事件
        $(document).on('keydown', function(e) {
            switch(e.keyCode) {
                case 37: // 左箭头
                    $magazine.turn('previous');
                    break;
                case 39: // 右箭头
                    $magazine.turn('next');
                    break;
            }
        });
    }

    // 显示提示信息
    showAlert(msg) {
        const $alert = $("#turn-js-alert");
        clearTimeout(this.alertTimer);
        $alert.text(msg);
        $alert.fadeIn();
        this.alertTimer = setTimeout(() => {
            $alert.fadeOut();
        }, 1000);
    }

    // 销毁Turn.js实例，清理资源
    destroy() {
        try {
            // 获取magazine元素
            let magazine;
            if (this.canvas && this.canvas.tagName === 'CANVAS') {
                // 如果是画布元素，magazine元素是插入到画布后面的元素
                magazine = document.getElementById('turn-js-magazine');
            } else {
                // 如果不是画布元素，magazine元素是canvas的子元素
                magazine = this.canvas.querySelector('#turn-js-magazine');
            }
            
            if (magazine) {
                // 使用jQuery销毁Turn.js实例
                $(magazine).turn('destroy').remove();
                
                // 如果是画布元素，还需要移除插入的HTML结构
                if (this.canvas && this.canvas.tagName === 'CANVAS') {
                    // 显示原始画布
                    this.canvas.style.display = '';
                    
                    // 移除插入的HTML结构
                    const insertedMagazine = document.getElementById('turn-js-magazine');
                    const insertedAlert = document.getElementById('turn-js-alert');
                    
                    if (insertedMagazine) {
                        insertedMagazine.remove();
                    }
                    
                    if (insertedAlert) {
                        insertedAlert.remove();
                    }
                }
            }
            
            // 移除键盘事件监听
            $(document).off('keydown');
            
            console.log('错误: Turn.js instance destroyed successfully');
        } catch (error) {
            console.error('Error destroying Turn.js instance:', error);
        }
    }
}

// 将TurnJsPageEffect添加到全局作用域
window.TurnJsPageEffect = TurnJsPageEffect;