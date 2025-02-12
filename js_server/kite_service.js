const express = require('express');
const bodyParser = require('body-parser');
const { getSignature } = require('./kite_sign');

const app = express();
const port = process.env.PORT || 3002;

// 中间件
app.use(bodyParser.json());

// 错误处理中间件
app.use((err, req, res, next) => {
    console.error(err.stack);
    res.status(500).json({
        success: false,
        error: 'Internal Server Error'
    });
});

// 签名接口
app.post('/api/signature', async (req, res) => {
    try {
        const { mnemonic, proxy, message } = req.body;

        // 参数验证
        if (!mnemonic || !proxy || !message) {
            return res.status(400).json({
                success: false,
                error: 'Missing required parameters: mnemonic or proxy'
            });
        }

        // 获取签名
        const result = await getSignature(mnemonic, proxy, message);
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// 健康检查接口
app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
});

// 启动服务器
app.listen(port, () => {
    console.log(`Server is running on port ${port}`);
});
