// 控制台日志捕获脚本
(function() {
    // 保存原始的console方法
    const originalLog = console.log;
    const originalError = console.error;
    const originalWarn = console.warn;
    
    // 创建日志数组
    window.consoleLogs = [];
    
    // 重写console.log
    console.log = function() {
        // 调用原始方法
        originalLog.apply(console, arguments);
        
        // 添加到日志数组
        const args = Array.from(arguments);
        window.consoleLogs.push({
            type: 'log',
            message: args.join(' '),
            timestamp: new Date().toISOString()
        });
    };
    
    // 重写console.error
    console.error = function() {
        // 调用原始方法
        originalError.apply(console, arguments);
        
        // 添加到日志数组
        const args = Array.from(arguments);
        window.consoleLogs.push({
            type: 'error',
            message: args.join(' '),
            timestamp: new Date().toISOString()
        });
    };
    
    // 重写console.warn
    console.warn = function() {
        // 调用原始方法
        originalWarn.apply(console, arguments);
        
        // 添加到日志数组
        const args = Array.from(arguments);
        window.consoleLogs.push({
            type: 'warn',
            message: args.join(' '),
            timestamp: new Date().toISOString()
        });
    };
    
    // 添加获取日志的方法
    window.getConsoleLogs = function() {
        return window.consoleLogs;
    };
    
    // 添加清除日志的方法
    window.clearConsoleLogs = function() {
        window.consoleLogs = [];
    };
    
    // 添加显示日志的方法
    window.displayConsoleLogs = function() {
        const logs = window.getConsoleLogs();
        let output = '=== 控制台日志 ===\n';
        
        logs.forEach(log => {
            output += `[${log.timestamp}] [${log.type.toUpperCase()}] ${log.message}\n`;
        });
        
        return output;
    };
})();