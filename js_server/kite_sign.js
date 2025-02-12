const ethers = require('ethers');
const crypto = require('crypto');
const {SocksProxyAgent} = require("socks-proxy-agent");
const {FetchRequest} = require("ethers");
const rpcUrl='https://rpc.ankr.com/eth'

/**
 * 获取签名信息
 * @param {string} mnemonic - 助记词
 * @param {string} proxy - 代理地址
 * @param {string} message
 * @returns {Promise<{success: boolean, data?: any, error?: string}>}
 */
async function getSignature(mnemonic, proxy,message) {
    try {
        const wallet_proxy = proxy.replace('socks5', 'socks5h');
        const proxyAgent = new SocksProxyAgent(wallet_proxy);

        const fetch_req = new FetchRequest(rpcUrl);
        fetch_req.getUrlFunc = FetchRequest.createGetUrlFunc({
            agent: proxyAgent
        });

        const provider = new ethers.JsonRpcProvider(fetch_req);
        const wallet = ethers.Wallet.fromPhrase(mnemonic, provider);
        // 构造签名消息

        // 签名
        const signatureHex = await wallet.signMessage(message);
        const address = await wallet.getAddress();

        return {
            success: true,
            data: {
                message,
                signatureHex,
                address: address
            }
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
}

module.exports = {getSignature};
