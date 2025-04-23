import openai
import os
import pandas as pd
import time
from datetime import datetime
from rich import print as rprint
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
