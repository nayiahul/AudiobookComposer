/**
 * 书籍翻页效果
 * 实现类似真实书籍的翻页效果，双页竖排从右到左模式
 * 以两页中间为轴心，从左向右翻页
 */

// 使用统一的日志过滤机制，不重复重写console.log
// 如果app.js已经重写了console.log，则不再重写
if (typeof console.logFilter !== 'function') {
    // 只在app.js未设置日志过滤时才设置
    const originalConsoleLogBook = console.log;
    console.log = function(...args) {
        // 只允许错误级别的日志输出
        if (args.length > 0 && typeof args[0] === 'string' && args[0].includes('错误')) {
            originalConsoleLogBook.apply(console, args);
        }
    };
}

class BookPageTurnEffect {
    /**
     * 构造函数
     * @param {HTMLElement|string} container - 容器元素或ID
     * @param {Object} options - 配置选项
     */
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.getElementById(container) : container;
        this.options = Object.assign({
            width: this.container ? this.container.offsetWidth : 800,
            height: this.container ? this.container.offsetHeight : 600,
            pageWidth: 0,  // 单页宽度，初始化后计算
            pageHeight: 0, // 单页高度，初始化后计算
            duration: 800, // 翻页动画持续时间（毫秒）
            shadow: true,  // 是否显示翻页阴影
            cornerSize: 50, // 翻页角落大小
            autoCenter: true, // 是否自动居中
            pageFlipCallback: null // 翻页回调函数
        }, options);
        
        this.pages = [];
        this.currentPage = 0;
        this.isFlipping = false;
        this.flipAnimation = null;
        this.bookElement = null;
        this.leftPageElement = null;
        this.rightPageElement = null;
        this.flipPageElement = null;
        this.shadowElement = null;
        this.initialized = false;
    }

    /**
     * 初始化书籍翻页效果
     * @returns {Promise} - 返回一个Promise，表示初始化完成
     */
    async init() {
        return new Promise((resolve, reject) => {
            try {
                // 计算单页尺寸
                this.options.pageWidth = this.options.width / 2;
                this.options.pageHeight = this.options.height;
                
                // 创建书籍结构
                this.createBookStructure();
                
                // 添加事件监听
                this.addEventListeners();
                
                // 初始化完成
                this.initialized = true;
                resolve();
            } catch (error) {
                console.error('初始化书籍翻页效果失败:', error);
                reject(error);
            }
        });
    }

    /**
     * 创建书籍结构
     */
    createBookStructure() {
        // 清空容器
        this.container.innerHTML = '';
        
        // 创建书籍元素
        this.bookElement = document.createElement('div');
        this.bookElement.className = 'book-page-turn-container';
        this.bookElement.style.width = `${this.options.width}px`;
        this.bookElement.style.height = `${this.options.height}px`;
        this.bookElement.style.position = 'relative';
        this.bookElement.style.perspective = '2000px';
        this.bookElement.style.overflow = 'hidden';
        this.bookElement.style.backgroundColor = '#f5f5f5';
        
        // 创建左页
        this.leftPageElement = document.createElement('div');
        this.leftPageElement.className = 'book-page left-page';
        this.leftPageElement.style.position = 'absolute';
        this.leftPageElement.style.width = `${this.options.pageWidth}px`;
        this.leftPageElement.style.height = `${this.options.pageHeight}px`;
        this.leftPageElement.style.left = '0';
        this.leftPageElement.style.top = '0';
        this.leftPageElement.style.backgroundColor = '#fff';
        this.leftPageElement.style.boxShadow = 'inset -10px 0 20px rgba(0,0,0,0.1)';
        this.leftPageElement.style.zIndex = '1';
        this.leftPageElement.style.transformStyle = 'preserve-3d';
        this.leftPageElement.style.backfaceVisibility = 'hidden';
        
        // 创建右页
        this.rightPageElement = document.createElement('div');
        this.rightPageElement.className = 'book-page right-page';
        this.rightPageElement.style.position = 'absolute';
        this.rightPageElement.style.width = `${this.options.pageWidth}px`;
        this.rightPageElement.style.height = `${this.options.pageHeight}px`;
        this.rightPageElement.style.right = '0';
        this.rightPageElement.style.top = '0';
        this.rightPageElement.style.backgroundColor = '#fff';
        this.rightPageElement.style.boxShadow = 'inset 10px 0 20px rgba(0,0,0,0.1)';
        this.rightPageElement.style.zIndex = '1';
        this.rightPageElement.style.transformStyle = 'preserve-3d';
        this.rightPageElement.style.backfaceVisibility = 'hidden';
        
        // 创建翻页元素（初始隐藏）
        this.flipPageElement = document.createElement('div');
        this.flipPageElement.className = 'book-page flip-page';
        this.flipPageElement.style.position = 'absolute';
        this.flipPageElement.style.width = `${this.options.pageWidth}px`;
        this.flipPageElement.style.height = `${this.options.pageHeight}px`;
        this.flipPageElement.style.right = '0';
        this.flipPageElement.style.top = '0';
        this.flipPageElement.style.backgroundColor = '#fff';
        this.flipPageElement.style.zIndex = '10';
        this.flipPageElement.style.transformStyle = 'preserve-3d';
        this.flipPageElement.style.backfaceVisibility = 'hidden';
        this.flipPageElement.style.transformOrigin = 'left center';
        this.flipPageElement.style.display = 'none';
        
        // 创建翻页阴影元素（初始隐藏）
        this.shadowElement = document.createElement('div');
        this.shadowElement.className = 'book-page-shadow';
        this.shadowElement.style.position = 'absolute';
        this.shadowElement.style.width = `${this.options.pageWidth}px`;
        this.shadowElement.style.height = `${this.options.pageHeight}px`;
        this.shadowElement.style.right = '0';
        this.shadowElement.style.top = '0';
        this.shadowElement.style.zIndex = '5';
        this.shadowElement.style.display = 'none';
        this.shadowElement.style.pointerEvents = 'none';
        
        // 添加示例内容
        this.addSampleContent();
        
        // 组装书籍
        this.bookElement.appendChild(this.leftPageElement);
        this.bookElement.appendChild(this.rightPageElement);
        this.bookElement.appendChild(this.flipPageElement);
        this.bookElement.appendChild(this.shadowElement);
        this.container.appendChild(this.bookElement);
    }

    /**
     * 添加示例内容
     */
    addSampleContent() {
        // 左页内容
        const leftContent = document.createElement('div');
        leftContent.style.padding = '20px';
        leftContent.style.height = '100%';
        leftContent.style.boxSizing = 'border-box';
        leftContent.style.display = 'flex';
        leftContent.style.flexDirection = 'column';
        leftContent.style.justifyContent = 'center';
        leftContent.style.alignItems = 'center';
        leftContent.innerHTML = `
            <h2 style="margin-top: 0; text-align: center;">第 ${this.currentPage + 1} 页</h2>
            <p style="text-align: center;">这是左页内容，点击右侧翻页</p>
            <div style="margin-top: 20px; padding: 10px; border: 1px dashed #ccc; width: 80%;">
                <p>这是一些示例文本，用于展示双页竖排从右到左的翻页效果。</p>
                <p>翻页时，页面会以两页中间为轴心，从左向右翻动。</p>
            </div>
        `;
        this.leftPageElement.appendChild(leftContent);
        
        // 右页内容
        const rightContent = document.createElement('div');
        rightContent.style.padding = '20px';
        rightContent.style.height = '100%';
        rightContent.style.boxSizing = 'border-box';
        rightContent.style.display = 'flex';
        rightContent.style.flexDirection = 'column';
        rightContent.style.justifyContent = 'center';
        rightContent.style.alignItems = 'center';
        rightContent.innerHTML = `
            <h2 style="margin-top: 0; text-align: center;">第 ${this.currentPage + 2} 页</h2>
            <p style="text-align: center;">这是右页内容，点击此处翻页</p>
            <div style="margin-top: 20px; padding: 10px; border: 1px dashed #ccc; width: 80%;">
                <p>点击右页可以触发翻页动画。</p>
                <p>翻页效果模拟真实书籍的翻页体验。</p>
            </div>
        `;
        this.rightPageElement.appendChild(rightContent);
    }

    /**
     * 添加事件监听
     */
    addEventListeners() {
        // 右页点击事件 - 触发翻页
        this.rightPageElement.addEventListener('click', (e) => {
            if (!this.isFlipping) {
                this.flipNext();
            }
        });
        
        // 左页点击事件 - 向后翻页
        this.leftPageElement.addEventListener('click', (e) => {
            if (!this.isFlipping && this.currentPage > 0) {
                this.flipPrevious();
            }
        });
    }

    /**
     * 翻到下一页
     */
    flipNext() {
        if (this.isFlipping) return;
        
        this.isFlipping = true;
        
        // 设置翻页元素内容（当前右页的内容）
        this.flipPageElement.innerHTML = this.rightPageElement.innerHTML;
        this.flipPageElement.style.display = 'block';
        
        // 设置阴影
        if (this.options.shadow) {
            this.createShadow();
            this.shadowElement.style.display = 'block';
        }
        
        // 开始翻页动画
        this.flipPageElement.style.transition = `transform ${this.options.duration}ms ease-in-out`;
        this.flipPageElement.style.transform = 'rotateY(-180deg)';
        
        // 动画结束后
        setTimeout(() => {
            // 更新页面内容
            this.currentPage += 2;
            this.updatePageContent();
            
            // 重置翻页元素
            this.flipPageElement.style.transition = 'none';
            this.flipPageElement.style.transform = 'rotateY(0deg)';
            this.flipPageElement.style.display = 'none';
            
            // 隐藏阴影
            this.shadowElement.style.display = 'none';
            
            // 触发回调
            if (this.options.pageFlipCallback) {
                this.options.pageFlipCallback(this.currentPage);
            }
            
            this.isFlipping = false;
        }, this.options.duration);
    }

    /**
     * 翻到上一页
     */
    flipPrevious() {
        if (this.isFlipping || this.currentPage <= 0) return;
        
        this.isFlipping = true;
        
        // 设置翻页元素内容（当前左页的内容）
        this.flipPageElement.innerHTML = this.leftPageElement.innerHTML;
        this.flipPageElement.style.display = 'block';
        this.flipPageElement.style.transform = 'rotateY(180deg)';
        
        // 设置阴影
        if (this.options.shadow) {
            this.createShadow();
            this.shadowElement.style.display = 'block';
        }
        
        // 开始翻页动画
        this.flipPageElement.style.transition = `transform ${this.options.duration}ms ease-in-out`;
        this.flipPageElement.style.transform = 'rotateY(0deg)';
        
        // 动画结束后
        setTimeout(() => {
            // 更新页面内容
            this.currentPage -= 2;
            this.updatePageContent();
            
            // 重置翻页元素
            this.flipPageElement.style.transition = 'none';
            this.flipPageElement.style.transform = 'rotateY(0deg)';
            this.flipPageElement.style.display = 'none';
            
            // 隐藏阴影
            this.shadowElement.style.display = 'none';
            
            // 触发回调
            if (this.options.pageFlipCallback) {
                this.options.pageFlipCallback(this.currentPage);
            }
            
            this.isFlipping = false;
        }, this.options.duration);
    }

    /**
     * 创建翻页阴影
     */
    createShadow() {
        // 创建渐变阴影
        const gradient = `linear-gradient(90deg, 
            rgba(0, 0, 0, 0) 0%, 
            rgba(0, 0, 0, 0.2) 50%, 
            rgba(0, 0, 0, 0.4) 100%)`;
        
        this.shadowElement.style.background = gradient;
        this.shadowElement.style.opacity = '0.7';
    }

    /**
     * 更新页面内容
     */
    updatePageContent() {
        // 清空现有内容
        this.leftPageElement.innerHTML = '';
        this.rightPageElement.innerHTML = '';
        
        // 添加新内容
        this.addSampleContent();
    }

    /**
     * 销毁翻页效果
     */
    destroy() {
        if (this.initialized) {
            // 移除事件监听
            this.rightPageElement.removeEventListener('click', this.flipNext);
            this.leftPageElement.removeEventListener('click', this.flipPrevious);
            
            // 清空容器
            this.container.innerHTML = '';
            
            // 重置状态
            this.initialized = false;
            this.isFlipping = false;
        }
    }
}

// 将类添加到全局作用域
window.BookPageTurnEffect = BookPageTurnEffect;