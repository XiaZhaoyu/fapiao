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
from logger import init_log  # 假设 logger.py 中有一个 Logger 类或对象


class RequestAPI():
    def __init__(self, log_dir="history/", logger=None):
        if logger is None:
            self.logger = init_log(
                is_save=True,
                save_dir=log_dir,
            )
        else:
            self.logger = logger
        self.logger.info("RequestAPI initialized.")
        
    @staticmethod
    def generate_text(prompt, model="deepseek-r1:1.5b", stream=True, 
                    base_url = "http://129.28.161.150:6399/v1",
                    api_key = "your_openai_api_key") -> str | None:
        """
        使用 Ollama API 生成文本，支持流式响应
        :param prompt: 输入的提示信息(单一文本模态)
        :param model: 使用的模型名称，默认为 deepseek-r1:1.5b
        :return: 生成的文本
        """
        client = openai.OpenAI(
            base_url = base_url,
            api_key = api_key,
        )
        try:
            if stream:
                # response = openai.ChatCompletion.create(
                completion = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    # temperature=0.6,
                    # max_tokens=32768,
                    # top_p=0.95,
                    # frequency_penalty=0,
                    # presence_penalty=0
                )
                message = ""
                # 处理流式响应
                rprint("[bold green]以下是 LLM 输出：[/bold green]\n")
                for chunk in completion:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        print(content, end='', flush=True)
                        message += content
                print()
                return message
            else:
                # 发送非流式请求到 Ollama API
                completion = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                )
                # 提取模型的回复内容
                message = completion.choices[0].message.content
                rprint(f"[bold green]以下是 LLM 输出：[/bold green]\n{message}\n")
                print(completion.usage)
                return message

        except Exception as e:
            rprint(f"[red]请求发生错误: {e}[/red]")
            return None

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


    @staticmethod
    def generate_by_swift(prompts: str | List[str], model="Qwen/Qwen2.5-7B-Instruct") -> List:
        """
        使用 Swift API 生成文本，支持批量处理，但不支持流式响应。注意：模型响应的文本需要通过header_responses[i].choices[0].message.content进行处理
        """
        from swift.llm import PtEngine, RequestConfig, InferRequest

        os.environ['CUDA_VISIBLE_DEVICES'] = '0'
        engine = PtEngine(model, max_batch_size=2)
        request_config = RequestConfig(max_tokens=5120, temperature=0)
        if isinstance(prompts, str):
            prompts = [prompts]
        infer_requests = [
            InferRequest(messages=[{'role': 'user', 'content': prompt}]) for prompt in prompts
        ]
        responses = engine.infer(infer_requests, request_config)
        
        return responses

    def generate_by_ark(self, prompt:str, model:str, json_data:str="", stream=True) -> str:
        """
        使用火山引擎 API 生成文本，支持多模态输入和流式响应
        :param prompt: 输入的提示信息
        :param model: 使用的模型名称
        :param json_data: 可选的 JSON 输入
        :param stream: 是否使用流式响应
        :return: 生成的文本和 token 使用情况（usage），若不使用流式响应，则 usage 返回空字符串
        """
        from volcenginesdkarkruntime import Ark

        client = Ark(api_key="57c88c6d-05d0-4370-9ff0-81167f7e11d6")
        system_prompt = "- Carefully consider the user's question to ensure your answer is logical and makes sense.\n- Make sure your explanation is concise and easy to understand, not verbose.\n- Strictly return the answer in json format.\n- Strictly Ensure that the following answer is in a valid JSON format.\n- The output should be formatted as a JSON instance that conforms to the JSON schema below and do not add comments.\n\nHere is the output schema:\n'''\n{\n\t\"tax\": float,\n\t\"total\": float,\n\t\"date\": string,\n\t\"code\": string,\n\t\"judge\": string, //为发票类型判断符，分为“普通发票”“增值税发票”“铁路电子客票”三类，用于辅助判断是否需要填写税额\n\t\"item\": string\n}\n'''\n\n"
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
                model="doubao-1-5-pro-32k-250115",
                messages=messages,
                logprobs=False,
                max_tokens=4096,
                stream=True,
                stream_options={"include_usage":True},
                temperature=0.3,
                top_p=0.7,
                presence_penalty=0,
                response_format={"type": "json_object"}
            )
            for chunk in resp:
                if not chunk.choices:
                    usage = chunk.usage
                else:
                    content_piece = chunk.choices[0].delta.content
                    print(content_piece, end='', flush=True)
                    if content_piece:
                        full_content += content_piece
            print()
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            cached_tokens = usage.prompt_tokens_details.cached_tokens
            self.logger.info(f"Prompt tokens: {prompt_tokens}")
            self.logger.info(f"Completion tokens: {completion_tokens}")
            self.logger.info(f"Total tokens: {total_tokens}")
            self.logger.info(f"Cached tokens: {cached_tokens}")
            return full_content, usage

        else:
            resp = client.chat.completions.create(
                model="doubao-1-5-vision-pro-32k-250115",
                messages=messages,
                max_tokens=4096,
                stream=False,
                temperature=0.3,
                top_p=0.7,
            )
            return resp.choices[0].message.content, ""

    def image2base64(image_path: str) -> str:
        """
        将图片转换为 base64 编码
        :param image_path: 图片文件路径
        :return: base64 编码的字符串
        """
        import base64
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string
    
    def base642image(base64_str: str, output_path: str) -> None:
        """
        将 base64 编码的字符串转换为图片
        :param base64_str: base64 编码的字符串
        :param output_path: 输出图片文件路径
        :return: None
        """
        import base64
        with open(output_path, "wb") as image_file:
            image_file.write(base64.b64decode(base64_str))

def convert_excel_to_csv(input_file_path: str, output_file_path=None) -> None | str:
    # 检查文件扩展名是否为 .xlsx 或 .xls
    if not (input_file_path.endswith(('.xlsx', '.xls'))):
        rprint("[red]输入文件必须是 .xlsx 或 .xls 格式。[/red]")
        return None
    try:
        # 读取 Excel 文件
        df = pd.read_excel(input_file_path)
        # 将数据保存为 CSV 文件，并指定编码为 UTF-8
        if not output_file_path:
            base_name = os.path.splitext(input_file_path)[0]
            output_file_path = base_name + '.csv'
        if not os.path.exists(output_file_path):
            df.to_csv(output_file_path, index=False, encoding='utf-8')
        rprint(f"[green]文件已成功转换为 {output_file_path}。[/green]")
        
        return output_file_path
    except Exception as e:
        rprint(f"[red]转换过程中出现错误: {e}[/red]")

def read_files(path: str, is_md=False) -> str:
    """
    读取表格文件或文件夹中的表格文件（如遇xlsx文件，则先存为csv，再读取csv文件），并采用LangChain将表格解析为文本
    :param path: 表格文件路径或文件夹路径
    :return: 解析为文本的表格数据
    """
    all_csv_content = []

    def _process_file(_path):
        """处理单个文件"""
        if _path.lower().endswith(('.xlsx', '.xls')):
            convert_excel_to_csv(_path) 
            _path = _path.split('.')[0] + '.csv'
        if _path.lower().endswith('.csv'):
            if is_md:
                df = pd.read_csv(_path)
                csv_content = df.to_markdown()
            else:
                loader = CSVLoader(_path)       # 创建 CSVLoader 对象
                documents = loader.load()

                # for doc in documents:         # type: <class 'langchain_core.documents.base.Document'>
                #     print(doc.page_content)   # type: <class 'str'>
                csv_content = "\n".join([doc.page_content for doc in documents])
        else:
            rprint(f"[red]不支持的文件类型: {_path}[/red]")
            return ""

        return csv_content

    if os.path.isfile(path):
        content = _process_file(path)
        file_content = f"以下是 CSV 文件 {os.path.basename(path)} 的数据：\n\n{content}\n\n"
        all_csv_content.append(file_content)

    elif os.path.isdir(path):
        # 处理文件夹
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                content = _process_file(file_path)
                file_content = f"以下是 CSV 文件 {os.path.basename(path)} 的数据：\n\n{content}\n\n"
                all_csv_content.append(file_content)

    # 合并所有 Markdown 表格
    combined_csv_content = "\n\n".join(all_csv_content)
    return combined_csv_content

def save_history(result, is_table=False, model="", save_path=None, save_mode="w"):
    """
    保存处理结果到本地
    :param result: 处理结果
    :param is_table: 是否为表格数据
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    # 保存 LLM 输出到 history 文件夹
    if model:
        model = model.replace('/', '_')
    history_folder = f'history/{model}'

    os.makedirs(history_folder, exist_ok=True)

    if not save_path:
        save_path = f"{timestamp}.txt"
    history_file = os.path.join(history_folder, save_path)
    with open(history_file, save_mode, encoding='utf-8') as f:
        f.write(result)

    # 如果是表格数据，保存到 result 文件夹
    if is_table:
        result_folder = 'result'
        if not os.path.exists(result_folder):
            os.makedirs(result_folder)
        result_file = os.path.join(result_folder, f"{timestamp}.csv")
        try:
            df = pd.read_csv(pd.compat.StringIO(result), sep='\t')
            df.to_csv(result_file, index=False)
        except Exception as e:
            rprint(f"[red]保存表格数据时发生错误: {e}[/red]")

def case1(user_input, model="deepseek-r1:1.5b", stream=True):
    # 读取表格文件或文件夹中的表格文件
    if isinstance(file_path, list):
        all_csv_content = ""
        for path in file_path:
            all_csv_content += read_files(path)
    else:
        all_csv_content = read_files(file_path)
    # 生成文本
    full_prompt = f"你需要分析以下 CSV 文件的数据（可能不止一个）：\n\n{all_csv_content}\n\n==========\n\n{user_input}"

    rprint(f"[bold green]以下是用户输入的数据：[/bold green]\n\n{all_csv_content[:1000]}\n\n（读取的文件内容可能进行了截断，仅输出前1000个字符）\n\n以下是用户提示词：\n\n{user_input}")
    rprint(f"[bold green]输入token总数（估计）：{len(full_prompt)}[/bold green]")
    rprint(f"[bold green]使用的模型是：{model}[/bold green]")
    t1 = time.time()
    response = generate_text(full_prompt, model=model, stream=stream)
    t2 = time.time()
    rprint(f"[bold yellow]模型运行时间为：{t2-t1}秒")

    # 保存处理结果
    save_history(full_prompt + "\n\n" + '-'*30 + "\n\n"
                + f"使用的模型是：{model}" + "\n\n" + '-'*30 + "\n\n"
                + f"模型运行时间为：{t2-t1}秒" + "\n\n" + '-'*30 + "\n\n"
                + response, is_table=False, model=model)

    return response

if __name__ == "__main__":
    # file_path = ["data/table/资产负债表.xlsx"]
    # user_input = "在资产负债表中，“货币资金”的期末余额是多少"
    # model = "qwq:latest"
    # stream = True
    # case1(user_input, model=model, stream=stream)
    prompt = """# 任务目标\n从用户上传的发票图片中提取出发票类型判断符（judge）、发票税额（tax）、总额（total）、发票发生日期（date）、发票号（code）、项目名称（item）和销售方名称（sellname）。\n# 具体要求\n1. 发票种类判断符分为以下几类：普通发票、增值税发票、铁路电子客票\n2. 发票发生日期格式为：YYYY年MM月DD日\n3. 发票税额：若发票上不包含税额，则填写为0\n5. 项目名称：结合发票类型判断符（judge）进行判断，若为铁路电子客票，则填写“火车票”；否则填写发票上的“项目名称”，并用空格代替“*”；如果项目名称存在多行，则将各行项目名称以半角逗号“,”分割\n# 以下是用户上传的发票图片"""
    image = "/root/jupyter-space/data/invoice_parse/invoice-normal.jpg"
    api = RequestAPI(log_dir="history/invoice_parse")
    response, usage = api.generate_by_ark(prompt=prompt, model="doubao-1-5-vision-pro-32k-250115", image=image, stream=True)
