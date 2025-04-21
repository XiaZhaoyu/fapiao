import streamlit as st
import oss2
import requests
import json
import re
import sys
import io
import re
import json
import zipfile
import pandas as pd
import time
import pandas as pd
from model_generate import RequestAPI

def remove_base64_from_json(data):
    for key in data:
        content = data[key]["result"]["data"]["content"]
        index = content.find('[IM0]')
    if index != -1:
        data[key]["result"]["data"]["content"] = content[:index]
    return data

def parse_invoice(json_data) -> tuple[dict, dict]:
    """
    解析发票 JSON 数据，提取发票信息
    :param json_path: JSON 文件路径
    :return: JSON 格式的解析结果和使用情况
    """
    prompt = """# 任务目标\n从用户上传的发票 JSON 数据中提取出发票类型判断符（judge）、发票税额（tax）、总额（total）、发票发生日期（date）、发票号码（code）和项目名称（item）。\n# 具体要求\n1. 发票种类判断符分为以下几类：普通发票、增值税发票、铁路电子客票\n2. 发票发生日期格式为：YYYY年MM月DD日，不包含具体时间;如果发票类型为铁路电子客票，要选取车票出发时间（不包含具体时间）\n3. 发票税额：若发票上不包含税额，则填写为0\n5. 项目名称：结合发票类型判断符（judge）进行判断，若为铁路电子客票，则填写“火车票”；否则填写发票上的“项目名称”，并用空格代替“*”；如果项目名称存在多行，则将各行项目名称以半角逗号“,”分割\n6.在提取发票号码时，先忽略机器编号和校验码；注意发票号码为纯数字，不包含特殊符号（*）或者字母(A到Z)。如果信息包括发票代码和发票号码，则需要提取的内容code=发票代码+发票号码\n# 以下是用户上传的发票 JSON 数据"""
    api = RequestAPI()
    rep= api.generate_by_modelscope(prompt=prompt,json_data=json_data, stream=True,model="deepseek-chat")
    try:
        return json.loads(rep)
    except json.JSONDecodeError:
        control=r"[(.*?)]"
        matches= re.search(control, rep, re.DOTALL)
        rep1 = matches.group(1) if matches else "No content found"
        return json.loads(rep1)

# 阿里云 OSS 配置
auth = oss2.Auth('LTAI5t9kZL1yweMWkkY56ArR', 'Rnbl5EaBDjIgJ3pUuP3nMIROITP677')
# 修改为存储桶对应的正确端点
bucket = oss2.Bucket(auth, 'http://oss-cn-shanghai.aliyuncs.com', 'oss-pai-3l4o7vcoebkqt34f32-cn-shanghai')
# 页面配置
st.set_page_config(
    page_title="发票识别",
    page_icon="📚",
    layout="wide"
)

# 页面标题
st.title("📚 RSM发票填写助手")

# 获取token
def get_token():
    url = 'https://www.streams7.com/api/auth/login'
    headers = {
        'Content-Type': 'application/json',
        'Cookie': 'auth_token=kig4ljn3UpeYdtnDLBB5HT8G4s9YjSBSeXvN1GMHKGe7eTSw0r7wV5FOSSjvsxlFTGVzLYuz893gSltTGTwxQrGbiwzclCZefX2ipj5pgJ1Rr5fzgU7wY88hLLNWyiEY; auth_token.sig=S70W6N3MdVzUQN-5QiVFjVnMM2A'
    }
    data = {
        "type": "ticket",
        "ticket": "KRXfr0O81EiVAmVb1Rli8LTYC04MXKFy"
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        token = response.json().get('token')
        return token
    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP error occurred while getting token: {http_err}")
    except Exception as err:
        st.error(f"Other error occurred while getting token: {err}")
    return None


# 文档解析z
def analyze_document(token, pdf_url):
    url = 'https://www.streams7.com/api/search/service/document-analyze'
    headers = {
        'sec-ch-ua-platform': '"macOS"',
        'Referer': 'https://rsm.streams7.com/knowledge_base/chat',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'accept': 'text/event-stream',
        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        'Content-Type': 'application/json',
        'sec-ch-ua-mobile': '?0',
        'Authorization': f'Bearer {token}'
    }
    data = {
        "document": {
            "url": pdf_url
        }
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP error occurred while analyzing document: {http_err}")
    except Exception as err:
        st.error(f"Other error occurred while analyzing document: {err}")
    return None

##处理逻辑
## 生成附件一
def json_to_dataframe1(json_data):
    data = []
    for i, item in enumerate(json_data["outputList"], start=1):
        # 序号
        serial_number = i
        # 发生日期
        date = item["date"]
        # 购货方（发票抬头）
        if item["judge"] == "铁路电子客票":
            invoice_title = "不适用"
        else:
            invoice_title = "容诚会计师事务所（特殊普通合伙）上海分所"
        # 票据金额
        ticket_amount = item["total"]
        # 进项税额
        if item["judge"] == "普通发票":
            input_tax = 0
        elif item["judge"] == "增值税发票":
            input_tax = item["tax"]
        elif item["judge"] == "铁路电子客票":
            input_tax = round(item["total"] / 1.09 * 0.09,2)
        # 费用摘要和票据种类
        item_str = item["item"]
        if re.search(r'住宿服务|代订住宿|住宿费', item_str):
            expense_summary = "住宿费"
            ticket_type = "住宿票"
            if re.search(r'代订住宿', item_str):
                remark = "携程/飞猪等酒店发票"
            else:
                remark = ""
        elif re.search(r'国内航空旅客运输服务|代订机票', item_str):
            expense_summary = "交通费"
            if re.search(r'代订机票', item_str):
                ticket_type = "其他运输服务电子发票"
                remark = "携程/飞猪等机票发票"
            else:
                ticket_type = "机票"
                remark = ""
        elif re.search(r'客运服务费', item_str):
            expense_summary = "交通费"
            ticket_type = "打车软件发票"
            remark = ""
        elif re.search(r'餐饮服务', item_str):
            expense_summary = "餐费"
            ticket_type = "餐票"
            remark = ""
        else:
            if item["judge"] == "铁路电子客票":
                expense_summary = "交通费"
                ticket_type = "火车票"
            else:
                expense_summary = item["item"]
                ticket_type = item["judge"]
            remark = ""

        data.append([serial_number, date, expense_summary, invoice_title,
                     ticket_type, ticket_amount, input_tax, remark])
    columns = ["序号", "发生日期", "费用摘要", "购货方（发票抬头）",
               "票据种类", "票据金额", "进项税额", "备注"]
    df = pd.DataFrame(data, columns=columns)
    return df

## 生成附件二
def json_to_dataframe2(json_data):
    data = []
    for i, item in enumerate(json_data["outputList"], start=1):
        item_str = item["item"]
        # 序号
        serial_number = i
        # 发生日期
        date = item["date"]
        # 购货方（发票抬头）
        if item["judge"] == "铁路电子客票":
            invoice_title = "不适用"
        else:
            invoice_title = "容诚会计师事务所（特殊普通合伙）上海分所"
        # 票据金额
        ticket_amount = item["total"]
        # 进项税额
        if item["judge"] == "普通发票":
            input_tax = 0
        elif item["judge"] == "增值税发票":
            input_tax = item["tax"]
        elif item["judge"] == "铁路电子客票":
            input_tax = round(item["total"] / 1.09 * 0.09,2)
        # 票据种类
        if re.search(r'住宿服务|代订住宿', item_str):
            ticket_type = "住宿票"
            if re.search(r'代订住宿', item_str):
                remark = "携程/飞猪等酒店发票"
            else:
                remark = ""
        elif re.search(r'国内航空旅客运输服务|代订机票', item_str):
            if re.search(r'代订机票', item_str):
                ticket_type = "其他运输服务电子发票"
                remark = "携程/飞猪等机票发票"
            else:
                ticket_type = "机票"
                remark = ""
        elif re.search(r'客运服务费', item_str):
            ticket_type = "打车软件发票"
            remark = ""
        elif re.search(r'餐饮服务', item_str):
            ticket_type = "餐票"
            remark = ""
        else:
            if item["judge"] == "铁路电子客票":
                ticket_type = "火车票"
            else:
                ticket_type = item["judge"]
            remark = ""
        number_bx=""
        data.append([serial_number, date, invoice_title,ticket_type, 
                    ticket_amount, input_tax,number_bx,remark])

    columns = ["序号", "发生日期", "购货方（发票抬头）","票据种类", 
            "票据金额", "进项税额", "报销单号","备注"]
    df = pd.DataFrame(data, columns=columns)
    # 删除进项税额为 0 的行
    df = df[(df["进项税额"] != 0) & df["票据种类"].isin(["火车票", "打车软件发票", "机票", "其他运输服务电子发票"])]
    # 重新排序序号
    df = df.reset_index(drop=True)
    df["序号"] = df.index + 1
    return df

## 生成附件三
def json_to_dataframe3(json_data):
    data = []
    for i, item in enumerate(json_data["outputList"], start=1):
        # 序号
        serial_number = i
        # 日期
        date = item["date"]
        # 发票代码
        invoice_id=item["code"][0:12]
        # 发票号码
        invoice_number=item["code"][12:]
        # 开票内容
        content=item["item"]
        if content=='住宿费' or content=='住宿服务':
            content="住宿服务 住宿费"
        elif content=='运输服务|客运服务费':
            content="运输服务 客运服务费"
        elif content=='餐饮服务':
            content="餐饮服务 餐饮服务"
        else:
            content = content.replace(",", "\n")
        # 金额
        ticket_amount=item["total"]
        # 报销人和报销单号
        people=''
        number_bx=''
        
        data.append([serial_number, date, invoice_id,invoice_number,content,
                     ticket_amount, people,number_bx])

    columns = ["序号", "日期", "发票代码","发票号码", "开票内容", 
               "金额", "报销人", "报销单号"]
    df = pd.DataFrame(data, columns=columns)
    return df

def main():
    # 上传多个 PDF 文件
    uploaded_files = st.file_uploader("第一步：请上传发票文件",type=["pdf"], accept_multiple_files=True)
    if uploaded_files:
        file_count = len(uploaded_files)
        pdf_count = sum(1 for f in uploaded_files if f.type == "application/pdf")
        image_count = file_count - pdf_count
        st.success(f"成功上传 {file_count} 个文件（{pdf_count} 个 PDF）")
    # 添加按钮
    analyze_button = st.button("第二步：点击解析发票文件")
    
    if uploaded_files and analyze_button:
        token = get_token()
        if token:
            all_results = {}
            for uploaded_file in uploaded_files:
                # 上传文件到 OSS
                oss_key = f'uploads/{uploaded_file.name}'
                result = bucket.put_object(oss_key, uploaded_file)
                if result.status == 200:
                    # 生成带签名的 URL
                    pdf_url = bucket.sign_url('GET', oss_key, 3600)  # 签名 URL 有效期为 3600 秒
                    # 解析文档
                    result = analyze_document(token, pdf_url)
                    if result:
                        all_results[uploaded_file.name] = result
                    time.sleep(0.5)
            if all_results:
                jsonfiles = {"outputList": []}
                # 将结果转换为 JSON 字符串
                contents = []
                for item in all_results.values():
                    contents.append(item["result"]["data"]["content"])
                all_results=remove_base64_from_json(all_results)
                # 定义正则表达式模式，匹配 [IM0]:data:image/ 开头的行及后续所有内容（包括换行符）
                pattern = re.compile(r'\[IM0\]:data:image/.*', re.DOTALL)

                for pdf_key in all_results:
                    # 提取 content 内容
                    content = all_results[pdf_key]['result']['data']['content']
                    # 使用正则表达式替换匹配到的内容为空字符串
                    cleaned_content = re.sub(pattern, '', content)
                    # 更新字典中的 content
                    all_results[pdf_key]['result']['data']['content'] = cleaned_content
                for i in contents:
                    json_result= parse_invoice(i)
                    jsonfiles["outputList"].append(json_result)
                json_str = json.dumps(all_results, indent=2,ensure_ascii=False)
                #st.download_button(
                        #label="第三步：下载EXCEL压缩包",
                        #data=json_str,
                        #file_name="all_results.json",
                        #mime="application/json",  # 指定 MIME 类型
                    #)
                # 创建下载按钮列
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                        # 处理 col2 的文件
                        csv_1 = json_to_dataframe1(jsonfiles)
                        excel_buffer_1 = io.BytesIO()
                        csv_1.to_excel(excel_buffer_1, index=False, engine='openpyxl')
                        excel_buffer_1.seek(0)
                        zipf.writestr("附件1_费用开支明细表_XXX_XXX年度产品审计、清算审计、产品验资及RWA鉴证.xlsx",
                                    excel_buffer_1.getvalue())

                        # 处理 col3 的文件
                        csv_2 = json_to_dataframe2(jsonfiles)
                        if not csv_2.empty:
                            excel_buffer_2 = io.BytesIO()
                            csv_2.to_excel(excel_buffer_2, index=False, engine='openpyxl')
                            excel_buffer_2.seek(0)
                            zipf.writestr("附件2_可抵扣交通费明细表_XXX_XXX年度公募及专户产品审计.xlsx",
                                        excel_buffer_2.getvalue())

                        # 处理 col4 的文件
                        csv_3 = json_to_dataframe3(jsonfiles)
                        excel_buffer_3 = io.BytesIO()
                        csv_3.to_excel(excel_buffer_3, index=False, engine='openpyxl')
                        excel_buffer_3.seek(0)
                        zipf.writestr("附件3_电子发票登记表_XXX_XXX年度公募及专户产品审计.xlsx",
                                    excel_buffer_3.getvalue())

                    zip_buffer.seek(0)
                    st.download_button(
                        label="下载压缩包",
                        data=zip_buffer,
                        file_name="所有附件.zip",
                        mime="application/zip"
                    )

if __name__ == "__main__":
    main()

# 侧边栏说明
with st.sidebar:
    st.header("操作指南")
    st.markdown("""
    **1.上传发票文件**
    """)
    st.markdown("""
    **2.点击解析文档按钮**
    """)
    st.markdown("""
    **3.下载excel文件**
    """)
    st.header("""
    **注意**
    """)
    st.markdown("""
    **1）如果漏传发票，则继续补充上传，最终点击解析并下载excel即可**
    """)
