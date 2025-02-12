import asyncio
import json
import random
import sys
import time

from typing import Dict, Optional, Any

import aiohttp
import cloudscraper
import httpx
from fake_useragent import UserAgent
from loguru import logger
import aiofiles
# 初始化日志记录
logger.remove()
logger.add(sys.stdout, format='<g>{time:YYYY-MM-DD HH:mm:ss:SSS}</g> | <c>{level}</c> | <level>{message}</level>')

code_list = ["m4jdT5ua", "p9sGeEgv", "FgKtwuH6"]

async def stream_reader(
        url: str,
        json_data: Dict[str, Any],
        proxy:str,
        headers:dict
):
    # 设置超时
    timeout = aiohttp.ClientTimeout(total=None)  # 无限超时
    full_content = []
    is_success = True
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url,
                    json=json_data,
                    headers=headers,
                    proxy=proxy,
                    ssl=False
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"请求失败，状态码: {response.status}, 错误信息: {error_text}")

                async for line in response.content:
                    line = line.decode('utf-8').strip()

                    if not line:
                        continue

                    try:
                        # 检查是否是结束标记
                        if line == '[DONE]':
                            break

                        # 处理data:前缀
                        if line.startswith('data:'):
                            line = line[5:].strip()  # 移除'data:'前缀

                        if not line:  # 如果去掉前缀后为空，跳过
                            continue

                        json_response = json.loads(line)
                        choices = json_response.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            content = delta.get('content')
                            # 只有当content不为None时才添加到结果中
                            if content is not None:
                                full_content.append(content)
                            # 检查是否是结束标记
                            if choices[0].get('finish_reason') == 'stop':
                                break

                    except json.JSONDecodeError as e:
                        if '[DONE]' not in line:  # 忽略 [DONE] 的解析错误
                            logger.error(f"JSON解析错误: {e}, 原始数据: {line}")
                            is_success = False

    except Exception as e:
        print(f"发生错误: {e}")
        is_success = False

    return ''.join(full_content)


class ScraperReq:
    def __init__(self, proxy: dict, header: dict):
        self.scraper = cloudscraper.create_scraper(browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False,
        })
        self.proxy: dict = proxy
        self.header: dict = header

    def post_req(self, url, req_json, req_param):
        # logger.info(self.header)
        # logger.info(req_json)
        return self.scraper.post(url=url, headers=self.header, json=req_json, proxies=self.proxy, params=req_param)

    async def post_async(self, url, req_param=None, req_json=None):
        return await asyncio.to_thread(self.post_req, url, req_json, req_param)

    def get_req(self, url, req_param):
        return self.scraper.get(url=url, headers=self.header, params=req_param, proxies=self.proxy)

    async def get_async(self, url, req_param=None, req_json=None):
        return await asyncio.to_thread(self.get_req, url, req_param)

class KiteAIClient:
    JS_SERVER = 'http://127.0.0.1:3002'
    def __init__(self, mnemonic, proxy:str, main_header:dict, event_stream_header:dict=None, interact_header:dict=None):
        self.mnemonic = mnemonic
        self.proxy = proxy
        # 配置请求
        self.proxy_dict = {
            'http': proxy,
            'https': proxy
        }
        self.main_req = ScraperReq(self.proxy_dict, main_header)
        self.wallet_address = ''
        self.referral_id = random.choice(code_list)
        self.event_stream_req = ScraperReq(self.proxy_dict, event_stream_header)
        self.interact_req = ScraperReq(self.proxy_dict, interact_header)
        self.ques_list:list[str] = []

    async def get_signature(self, message:str):
        payload = {
            'mnemonic': self.mnemonic,
            'proxy': self.proxy,
            'message': message
        }
        # res = await .post_async(f'{self.JS_SERVER}/api/signature', req_json=payload)
        return await httpx.AsyncClient().post(f'{self.JS_SERVER}/api/signature', json=payload)

        # signature_hex = res.json()['data']['signatureHex']
        # address = res.json()['data']['address']
        # print(res.json())

    async def main_auth(self):
        self.main_req.header.update({'x-auth-token': None})
        url = "https://api-kiteai.bonusblock.io/api/auth/get-auth-ticket"
        # 生成动态nonce
        nonce = f"timestamp_{int(time.time() * 1000)}"
        payload = {
            "nonce": nonce
        }
        try:
            response = await self.main_req.post_async(
                url,
                req_json=payload
            )
            data = response.json()

            if data.get("success"):
                message = data.get("payload")
                # print(message)
                sign_res = await self.get_signature(message)
                signature_hex = sign_res.json()['data']['signatureHex']
                address = sign_res.json()['data']['address']
                self.wallet_address = address
                # 拿token
                auth_url = 'https://api-kiteai.bonusblock.io/api/auth/eth'
                payload = {
                    'blockchainName': 'ethereum',
                    'nonce': nonce,
                    'referralId': self.referral_id,
                    'signedMessage': signature_hex
                }

                login_res = await self.main_req.post_async(auth_url, req_json=payload)

                self.main_req.header.update({'x-auth-token': login_res.json()['payload']['session']['token']})
                logger.info(f"auth: {self.proxy}----{self.wallet_address}")
            else:
                raise Exception(f"{self.proxy}----{self.wallet_address}----{data.get('errors', 'Unknown error')}")
        except Exception as e:
            logger.error(f'{self.proxy}----{self.wallet_address}----main auth error, {e}')
            # print(e)

    async def get_status(self):
        status_url = 'https://api-kiteai.bonusblock.io/api/kite-ai/get-status'
        status_res = await self.main_req.get_async(status_url)

        payload = status_res.json()['payload']
        daily_agent_actions_xp = payload['dailyAgentActionsXp']
        logger.info(f"status: {self.proxy}----{self.wallet_address}: xp:{payload['userXp']}: ranK:{payload['rank']} dailyActionXp:{daily_agent_actions_xp}")

        return daily_agent_actions_xp

    async def interaction_ai_auth(self):

        text = random.choice(self.ques_list)
        try:
            async with aiofiles.open('./agen_urls', 'r') as file:
                urls = [line.strip() for line in (await file.readlines()) if line.strip()]
            url = random.choice(urls)
        except Exception as e:
            logger.error(f"Error reading agen_urls file: {e}")
            return
        payload = {"message": text, "stream": True}

        chat_res = await stream_reader(url, payload, self.proxy, self.event_stream_req.header)
        report_url = 'https://quests-usage-dev.prod.zettablock.com/api/report_usage'
        logger.info(f"chat: {self.proxy}----{self.wallet_address}: ques:{text}: answer:{chat_res}")
        report_json = {"wallet_address":self.wallet_address,"agent_id":"deployment_HlsY5TJcguvEA2aqgPliXJjg","request_text":text,"response_text":chat_res,"request_metadata":{}}
        res = await self.interact_req.post_async(url=report_url, req_json=report_json, req_param=None)
        logger.info(f"report: {self.proxy}----{self.wallet_address}----report-res:{res.text}")
        if 'Rate limit exceeded' in res.text:
            logger.info(f"report: {self.proxy}----{self.wallet_address}, 请求限制，睡眠1分钟")
            await asyncio.sleep(60)
            return
        interaction_id = res.json()['interaction_id']
        interaction_url = f'https://neo-dev.prod.zettablock.com/v1/inference?id={interaction_id}'
        res = await self.interact_req.get_async(interaction_url)
        logger.info(f'interaction-res: {self.proxy}----{self.wallet_address}----report-res: tx_hash:{res.json().get("tx_hash", "")}')
        if 'Failed to create/verify wallet in NeoDB' in res.text:
            return 'retry'
        await asyncio.sleep(5)
        res = await self.interact_req.get_async(interaction_url)
        logger.info(f'interaction-res: {self.proxy}----{self.wallet_address}----report-res: tx_hash:{res.json().get("tx_hash", "")}')
        stats_url = f'https://quests-usage-dev.prod.zettablock.com/api/user/{self.wallet_address}/stats'
        res = await self.interact_req.get_async(stats_url)
        logger.info(
            f'interaction-res: {self.proxy}----{self.wallet_address}----report-res: total_interact:{res.json()["total_interactions"]}')


    async def run_task(self):
        while True:
            try:
                await self.main_auth()
                daily_agent_actions_xp = await self.get_status()
                if daily_agent_actions_xp <= 200:
                    logger.info(f'{self.proxy}----{self.wallet_address}准备交互')
                    for i in range(20):
                        try:
                            res = await self.interaction_ai_auth()
                            if res is not None and res == 'retry':
                                break
                        except Exception as e:
                            logger.error(f'{self.proxy}----发生位置异常：{e}')
                        await asyncio.sleep(3)
                logger.success(f'完成一轮交互，{self.proxy}----{self.wallet_address}，睡眠2小时')
                await asyncio.sleep(60 * 60 * 2)
            except Exception as e:
                logger.error(f'{self.proxy}发送未知异常2：{e}，睡眠6小时')
                await asyncio.sleep(60 * 60 * 6)




async def run(acc):
    print(f'开始执行：{acc["proxy"]}')
    user_agent = UserAgent().chrome
    main_headers = {
        "accept-language": "zh-CN,zh;q=0.8",
        "content-type": "application/json",
        "origin": "https://testnet.gokite.ai",
        "priority": "u=1, i",
        "referer": "https://testnet.gokite.ai/",
        "user-agent": user_agent
    }

    interact_header = {
        "accept-language": "zh-CN,zh;q=0.8",
        "content-type": "application/json",
        "host": "quests-usage-dev.prod.zettablock.com",
        "origin": "https://agents.testnet.gokite.ai",
        "priority": "u=1, i",
        "referer": "https://agents.testnet.gokite.ai/",
        "user-agent": user_agent
    }

    event_stream_header = {

        "accept-language": "zh-CN,zh;q=0.8",
        "connection": "keep-alive",
        "content-type": "application/json",
        "origin": "https://agents.testnet.gokite.ai",
        "referer": "https://agents.testnet.gokite.ai/",
        "user-agent": user_agent
    }
    
    kite = KiteAIClient(acc['mnemonic'], acc['proxy'], main_headers, event_stream_header, interact_header)
    kite.ques_list = acc['ques']
    await kite.run_task()



async def main():
    ques_list = []
    with open('./web3_questions.txt', 'r', encoding='utf-8') as file:
        for line in file.readlines():
            ques = line.strip()
            ques_list.append(ques)


    accs = []
    with open('./acc', 'r', encoding='utf-8') as file:
        for line in file.readlines():
            mnemonic, proxy = line.strip().split('----')
            accs.append({
                'mnemonic': mnemonic,
                'proxy': proxy,
                'ques': ques_list
            })

    tasks = [run(acc) for acc in accs]
    await asyncio.gather(*tasks)
if __name__ == "__main__":
    logger.info('🚀 [ILSH] KITE v1.0 | Airdrop Campaign Live')
    logger.info('🌐 ILSH TG Community: t.me/ilsh_auto')
    logger.info('🐦 X(Twitter): https://x.com/hashlmBrian')
    logger.info('☕ Pay meCoffe：USDT（TRC20）: TAiGnbo2isJYvPmNuJ4t5kAyvZPvAmBLch')
    asyncio.run(main())
