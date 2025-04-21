import openai
import os
import pandas as pd
import time
from datetime import datetime
from rich import print as rprint
from langchain_community.document_loaders import CSVLoader
from typing import List
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))


class RequestAPI():        
    @staticmethod
    def generate_by_modelscope(prompt, model:str, stream=True, json_data:str="") -> str | None:
        """
        使用 ModelScope API 生成文本，支持流式响应
        """
        client = openai.OpenAI(
            api_key="sk-bf3698390f3b40dd8435cb73169a7437", # 请替换成您的ModelScope SDK Token
            base_url="https://api.deepseek.com"
        )
        system_prompt = "- Carefully consider the user's question to ensure your answer is logical and makes sense.\n- Make sure your explanation is concise and easy to understand, not verbose.\n- Strictly return the answer in a JSON array format, where each element in the array is a JSON object conforming to the following schema:\n{\n    \"tax\": float,\n    \"total\": float,\n    \"date\": string,\n    \"code\": string,\n    \"judge\": string, \n    \"item\": string\n}\n- Do not add any additional text, comments(), or explanations in the output. //为发票类型判断符，分为“普通发票”“增值税发票”“铁路电子客票”三类，用于辅助判断是否需要填写税额\n\t\"item\": string\n}\n'''\n\n"
        user_content = [
            {"text": prompt, "type": "text"},
        ]
        if json_data:
            user_content.append({"text": json_data, "type": "text"})
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        full_content = ""
        if stream:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                logprobs=False,
                max_tokens=4096,
                stream=True,
                stream_options={"include_usage":True},
                temperature=0.3,
                top_p=0.7,
                presence_penalty=0,
                response_format={
                    'type': 'json_object'
                }
            )
            for chunk in resp:
                content_piece = chunk.choices[0].delta.content
                print(content_piece, end='', flush=True)
                if content_piece:
                    full_content += content_piece
            return full_content

        else:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=4096,
                stream=False,
                temperature=0.3,
                top_p=0.7,
                response_format={
                    'type': 'json_object'
                }
            )
            return resp.choices[0].message.content, ""

if __name__ == "__main__":
    prompt = """# 任务目标\n从用户上传的发票图片中提取出发票类型判断符（judge）、发票税额（tax）、总额（total）、发票发生日期（date）、发票号（code）、项目名称（item）和销售方名称（sellname）。\n# 具体要求\n1. 发票种类判断符分为以下几类：普通发票、增值税发票、铁路电子客票\n2. 发票发生日期格式为：YYYY年MM月DD日\n3. 发票税额：若发票上不包含税额，则填写为0\n5. 项目名称：结合发票类型判断符（judge）进行判断，若为铁路电子客票，则填写“火车票”；否则填写发票上的“项目名称”，并用空格代替“*”；如果项目名称存在多行，则将各行项目名称以半角逗号“,”分割\n# 以下是用户上传的发票图片"""
    image = "/root/jupyter-space/data/invoice_parse/invoice-normal.jpg"
    api = RequestAPI(log_dir="history/invoice_parse")
    response, usage = api.generate_by_ark(prompt=prompt, model="doubao-1-5-vision-pro-32k-250115", image=image, stream=True)
