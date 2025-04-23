# app/Dockerfile

FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# RUN git clone https://github.com/XiaZhaoyu/fapiao.git
# 切换到克隆仓库的目录
WORKDIR /app/fapiao

COPY ./ ./

# 设置 PATH 环境变量
ENV PATH="/root/.local/bin:${PATH}"

# 使用阿里云镜像源安装依赖
RUN pip3 install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 暴露端口
EXPOSE 8501

# 启动 streamlit 应用
CMD ["streamlit", "run", "发票识别.py"]
# CMD ["/bin/bash"]
