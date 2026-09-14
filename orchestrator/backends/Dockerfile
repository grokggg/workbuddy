# Dockerfile —— M35 本机 Docker 后端(兜底)
# 用户本机构建, 提供完整分析环境

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc gdb binutils file python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    capstone pyelftools pefile angr unicorn

WORKDIR /workspace
COPY . /workspace

ENTRYPOINT ["python3", "unified-analysis/analysis_all.py"]
