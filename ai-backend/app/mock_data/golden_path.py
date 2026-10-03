"""黄金路径预制数据（MOCK_MODE 或真实 API 故障降级时使用）。

默认演示主题：两周入门扩散模型并做出图像生成 Demo。
前端联调期间所有端点都有稳定、确定的返回，不依赖网络与余额。
"""
import re
from typing import Optional

GOLDEN_KEYWORDS = ("扩散", "diffusion", "ddpm", "生成图像", "图像生成", "stable diffusion")


def _is_golden(goal: str) -> bool:
    g = (goal or "").lower()
    return any(k.lower() in g for k in GOLDEN_KEYWORDS)


# ---------------- Scholar：目标澄清 ----------------
def clarify(goal: str, user_message: str) -> tuple[str, bool]:
    if _is_golden(goal) or _is_golden(user_message):
        return (
            "很好，学习扩散模型并做出一个图像生成 Demo，是一条非常经典的路径！\n\n"
            "为了给你定制路线，我还想确认两点：\n"
            "1. 你的 Python 和深度学习基础如何？能否看懂 PyTorch 代码？\n"
            "2. 这两周你每天大概能投入多少小时？最终希望交付的是"
            "「跑通一个现成模型生成图片」，还是「在某个数据集上做微调」？",
            False,
        )
    return (
        f"收到你的目标：「{goal or user_message}」。我是你的 Scholar Agent，"
        "在为你规划路线前，想先了解：\n"
        "1. 你目前在这个方向的基础如何？\n"
        "2. 你计划投入多长时间，最终想做出什么成果？",
        False,
    )


def clarify_after_followup() -> tuple[str, bool]:
    return (
        "明白了！你具备 Python/PyTorch 基础，每天可投入 3 小时、为期两周，"
        "最终目标是跑通扩散模型并生成自己的图片作品。\n\n"
        "目标已经清晰，下面我为你生成专属学习路线，路线会引导你依次经过 "
        "X Gate、Library 图书馆、Professor Office 教授办公室和 Research Lab 实验室。",
        True,
    )


# ---------------- Scholar：路线图 ----------------
def _generic_roadmap(goal: str) -> dict:
    return {
        "title": f"「{goal}」两周学习与实践路线",
        "summary": "从目标确认出发，经过资料学习、教授答疑到实验室动手，最终做出可展示的成果。",
        "estimated_duration": "2 周",
        "stages": [
            {
                "id": "stage-1",
                "name": "X Gate · 目标确认",
                "space": "gate",
                "objective": "明确学习目标、现有基础与最终交付物",
                "tasks": [
                    {
                        "id": "t-1-1",
                        "title": "目标拆解与基础自评",
                        "description": f"围绕「{goal}」明确最终成果形态，自评先修知识，"
                        "形成一份一页纸的学习目标声明。",
                        "space": "gate",
                        "deliverable": "学习目标声明（含最终成果定义）",
                        "resources": [],
                        "status": "pending",
                    }
                ],
            },
            {
                "id": "stage-2",
                "name": "Library · 资料学习",
                "space": "library",
                "objective": "系统检索并精读核心资料，建立知识框架",
                "tasks": [
                    {
                        "id": "t-2-1",
                        "title": "核心资料检索与泛读",
                        "description": "在 Library 检索该方向的综述、经典教材与官方文档，"
                        "建立知识地图，标注 3-5 份核心材料。",
                        "space": "library",
                        "deliverable": "带注释的阅读清单与知识脑图",
                        "resources": [
                            {"title": "arXiv 论文检索", "type": "tool", "url": "https://arxiv.org/"},
                            {"title": "Google Scholar", "type": "tool", "url": "https://scholar.google.com/"},
                        ],
                        "status": "pending",
                    },
                    {
                        "id": "t-2-2",
                        "title": "核心材料精读笔记",
                        "description": "精读 2-3 份核心材料，用自己的话复述关键概念，记录疑问清单。",
                        "space": "library",
                        "deliverable": "精读笔记 + 疑问清单",
                        "resources": [],
                        "status": "pending",
                    },
                ],
            },
            {
                "id": "stage-3",
                "name": "Professor Office · 研讨答疑",
                "space": "professor_office",
                "objective": "带着疑问与 AI Professor 研讨，检验理解",
                "tasks": [
                    {
                        "id": "t-3-1",
                        "title": "核心概念研讨",
                        "description": "把精读中的疑问带入教授办公室，通过问答与类比彻底搞清核心机制。",
                        "space": "professor_office",
                        "deliverable": "概念理解记录（含费曼式复述）",
                        "resources": [],
                        "status": "pending",
                    }
                ],
            },
            {
                "id": "stage-4",
                "name": "Research Lab · 动手产出",
                "space": "lab",
                "objective": "在实验室完成实践，做出最终成果",
                "tasks": [
                    {
                        "id": "t-4-1",
                        "title": "最小可行实践",
                        "description": "在 Lab 中按导师给出的步骤跑通最小 Demo，验证核心流程。",
                        "space": "lab",
                        "deliverable": "可运行的最小 Demo",
                        "resources": [],
                        "status": "pending",
                    },
                    {
                        "id": "t-4-2",
                        "title": "个性化扩展与成果整理",
                        "description": "在最小 Demo 基础上加入自己的数据或创意，整理为可展示的作品与报告。",
                        "space": "lab",
                        "deliverable": "最终作品 + 项目报告",
                        "resources": [],
                        "status": "pending",
                    },
                ],
            },
        ],
        "final_outcome": f"围绕「{goal}」的一个可运行 Demo 与一份项目研究报告",
    }


def _diffusion_roadmap() -> dict:
    return {
        "title": "两周入门扩散模型：从数学直觉到图像生成 Demo",
        "summary": "X Gate 确认目标后，在 Library 精读 DDPM 等经典论文，"
        "在 Professor Office 攻克反向扩散与引导原理，最终在 Lab 跑通并生成自己的图片作品。",
        "estimated_duration": "2 周（每天约 3 小时）",
        "stages": [
            {
                "id": "stage-1",
                "name": "X Gate · 目标确认",
                "space": "gate",
                "objective": "确认基础与目标，建立两周冲刺契约",
                "tasks": [
                    {
                        "id": "t-1-1",
                        "title": "基础自评与目标锁定",
                        "description": "确认 Python/PyTorch 基础与 GPU 环境，锁定最终成果："
                        "跑通扩散模型并生成一组自己的图片作品。",
                        "space": "gate",
                        "deliverable": "学习目标声明 + 环境清单",
                        "resources": [
                            {"title": "PyTorch 官方安装指南", "type": "tool", "url": "https://pytorch.org/get-started/locally/"}
                        ],
                        "status": "pending",
                    }
                ],
            },
            {
                "id": "stage-2",
                "name": "Library · 扩散模型基础",
                "space": "library",
                "objective": "建立扩散模型的数学直觉，精读奠基论文",
                "tasks": [
                    {
                        "id": "t-2-1",
                        "title": "补先修：概率与生成模型基础",
                        "description": "复习高斯分布、贝叶斯与 ELBO 的直觉，了解 VAE/GAN 与扩散模型的定位差异。",
                        "space": "library",
                        "deliverable": "一页纸先修知识笔记",
                        "resources": [
                            {"title": "What are Diffusion Models?（Lilian Weng）", "type": "article",
                             "url": "https://lilianweng.github.io/posts/2021-07-11-diffusion-models/"}
                        ],
                        "status": "pending",
                    },
                    {
                        "id": "t-2-2",
                        "title": "精读 DDPM 论文",
                        "description": "精读《Denoising Diffusion Probabilistic Models》，"
                        "理解前向加噪、训练目标与反向去噪采样，整理推导笔记。",
                        "space": "library",
                        "deliverable": "DDPM 精读笔记 + 公式推导",
                        "resources": [
                            {"title": "Denoising Diffusion Probabilistic Models (Ho et al., 2020)",
                             "type": "paper", "url": "https://arxiv.org/abs/2006.11239"},
                            {"title": "Score-Based Generative Modeling through SDEs (Song et al., 2021)",
                             "type": "paper", "url": "https://arxiv.org/abs/2011.13456"},
                        ],
                        "status": "pending",
                    },
                    {
                        "id": "t-2-3",
                        "title": "了解 Stable Diffusion 与潜空间扩散",
                        "description": "阅读 Stable Diffusion 论文与科普资料，理解 VAE 潜空间、"
                        "文本编码器与 Classifier-Free Guidance 的作用。",
                        "space": "library",
                        "deliverable": "Stable Diffusion 架构图笔记",
                        "resources": [
                            {"title": "High-Resolution Image Synthesis with Latent Diffusion Models",
                             "type": "paper", "url": "https://arxiv.org/abs/2112.10752"},
                        ],
                        "status": "pending",
                    },
                ],
            },
            {
                "id": "stage-3",
                "name": "Professor Office · 攻克难点",
                "space": "professor_office",
                "objective": "与 AI Professor 研讨最难的两个原理并接受检验",
                "tasks": [
                    {
                        "id": "t-3-1",
                        "title": "研讨：反向扩散为什么能去噪",
                        "description": "向 Professor 复述前向/反向过程，接受追问，"
                        "彻底搞清噪声预测网络与采样链的关系。",
                        "space": "professor_office",
                        "deliverable": "反向扩散费曼式讲解录音/笔记",
                        "resources": [],
                        "status": "pending",
                    },
                    {
                        "id": "t-3-2",
                        "title": "研讨：Classifier-Free Guidance",
                        "description": "理解 CFG 如何用条件/无条件预测之差控制生成强度，"
                        "并讨论 guidance scale 对画面的影响。",
                        "space": "professor_office",
                        "deliverable": "CFG 原理问答记录",
                        "resources": [],
                        "status": "pending",
                    },
                ],
            },
            {
                "id": "stage-4",
                "name": "Research Lab · 做出图像生成 Demo",
                "space": "lab",
                "objective": "跑通工业级工具链，生成并打磨自己的作品",
                "tasks": [
                    {
                        "id": "t-4-1",
                        "title": "跑通 diffusers 最小推理管线",
                        "description": "使用 HuggingFace diffusers 加载 Stable Diffusion，"
                        "本地跑通文生图，记录不同 prompt 与参数的效果。",
                        "space": "lab",
                        "deliverable": "可运行的文生图 Notebook/脚本 + 首批生成图",
                        "resources": [
                            {"title": "Diffusers 官方文档", "type": "tool",
                             "url": "https://huggingface.co/docs/diffusers"},
                        ],
                        "status": "pending",
                    },
                    {
                        "id": "t-4-2",
                        "title": "参数实验与个人作品",
                        "description": "系统实验 steps、guidance scale、negative prompt，"
                        "确定一个主题，产出一组风格统一的个人作品。",
                        "space": "lab",
                        "deliverable": "参数实验记录 + 主题作品集（6-9 张）",
                        "resources": [],
                        "status": "pending",
                    },
                    {
                        "id": "t-4-3",
                        "title": "整理项目报告与展示",
                        "description": "把原理笔记、实验记录和作品整理为项目报告，"
                        "录制 1 分钟生成过程演示，形成最终成果。",
                        "space": "lab",
                        "deliverable": "项目报告 + 演示视频",
                        "resources": [],
                        "status": "pending",
                    },
                ],
            },
        ],
        "final_outcome": "一个可运行的扩散模型文生图 Demo、一组个人图像作品，以及一份原理与实验兼备的项目报告",
    }


def roadmap(goal: str) -> dict:
    if _is_golden(goal):
        return _diffusion_roadmap()
    return _generic_roadmap(goal or "你选择的研究主题")


# ---------------- Library：检索（Phase 2 替换为真实 RAG） ----------------
_LIBRARY_DOCS = [
    {"title": "Denoising Diffusion Probabilistic Models",
     "type": "paper", "url": "https://arxiv.org/abs/2006.11239",
     "snippet": "DDPM 奠基论文：用固定的前向加噪过程与可学习的反向去噪过程生成图像。"},
    {"title": "High-Resolution Image Synthesis with Latent Diffusion Models",
     "type": "paper", "url": "https://arxiv.org/abs/2112.10752",
     "snippet": "Stable Diffusion 背后的潜空间扩散，在 VAE 压缩空间中运行扩散，大幅降低算力。"},
    {"title": "Score-Based Generative Modeling through SDEs",
     "type": "paper", "url": "https://arxiv.org/abs/2011.13456",
     "snippet": "用随机微分方程统一扩散与 score-based 生成模型的理论框架。"},
    {"title": "What are Diffusion Models?（Lilian Weng）",
     "type": "article", "url": "https://lilianweng.github.io/posts/2021-07-11-diffusion-models/",
     "snippet": "扩散模型最受欢迎的入门长文，数学与直觉兼顾。"},
    {"title": "HuggingFace Diffusers 文档",
     "type": "tool", "url": "https://huggingface.co/docs/diffusers",
     "snippet": "工业级扩散模型推理/训练工具库，含大量可运行示例。"},
]


def library_docs(query: str, top_k: int = 5) -> list[dict]:
    q = (query or "").lower()
    if not q:
        return _LIBRARY_DOCS[:top_k]
    tokens = [t for t in re.split(r"\s+", q) if t] + re.findall(r"[一-龥]{2,}", q)

    def score(doc):
        hay = (doc["title"] + doc["snippet"]).lower()
        return sum(1 for t in tokens if t and t.lower() in hay)

    ranked = sorted(_LIBRARY_DOCS, key=score, reverse=True)
    hits = [d for d in ranked if score(d) > 0]
    return (hits or _LIBRARY_DOCS)[:top_k]


# ---------------- Library：arXiv 最新论文（mock） ----------------
_MOCK_ARXIV_PAPERS = [
    {"title": "Denoising Diffusion Probabilistic Models",
     "authors": ["Jonathan Ho", "Ajay Jain", "Pieter Abbeel"],
     "year": "2020", "url": "https://arxiv.org/abs/2006.11239",
     "snippet": "We present high quality image synthesis results using diffusion probabilistic models, a class of latent variable models inspired by considerations from nonequilibrium thermodynamics."},
    {"title": "High-Resolution Image Synthesis with Latent Diffusion Models",
     "authors": ["Robin Rombach", "Andreas Blattmann", "Dominik Lorenz", "Patrick Esser", "Björn Ommer"],
     "year": "2022", "url": "https://arxiv.org/abs/2112.10752",
     "snippet": "By crossing the limits of conventional pixel-based diffusion models, we propose latent diffusion models (LDMs) which operate in the latent space of a pretrained autoencoder."},
    {"title": "Score-Based Generative Modeling through Stochastic Differential Equations",
     "authors": ["Yang Song", "Jascha Sohl-Dickstein", "Diederik P. Kingma", "Abhishek Kumar", "Stefano Ermon", "Ben Poole"],
     "year": "2021", "url": "https://arxiv.org/abs/2011.13456",
     "snippet": "We introduce a unified framework for score-based generative models by generalizing diffusion processes and Langevin dynamics into stochastic differential equations (SDEs)."},
    {"title": "Denoising Diffusion Implicit Models",
     "authors": ["Jiaming Song", "Chenlin Meng", "Stefano Ermon"],
     "year": "2021", "url": "https://arxiv.org/abs/2010.02502",
     "snippet": "We present denoising diffusion implicit models (DDIMs), a more efficient class of iterative implicit probabilistic models with the same training procedure as DDPMs."},
    {"title": "LoRA: Low-Rank Adaptation of Large Language Models",
     "authors": ["Edward J. Hu", "Yelong Shen", "Phillip Wallis", "Zeyuan Allen-Zhu", "Yuanzhi Li", "Shean Wang", "Lu Wang"],
     "year": "2022", "url": "https://arxiv.org/abs/2106.09685",
     "snippet": "We propose Low-Rank Adaptation, or LoRA, which freezes the pretrained model weights and injects trainable rank decomposition matrices into each layer of the Transformer architecture."},
    {"title": "Learning Transferable Visual Models From Natural Language Supervision",
     "authors": ["Alec Radford", "Jong Wook Kim", "Chris Hallacy", "Aditya Ramesh", "Gabriel Goh", "Sandhini Agarwal", "Girish Sastry", "Amanda Askell", "Pamela Mishkin", "Jack Clark", "Gretchen Krueger", "Ilya Sutskever"],
     "year": "2021", "url": "https://arxiv.org/abs/2103.00020",
     "snippet": "We present a simple pre-training task as an efficient and scalable way to learn SOTA image representations from scratch: contrastive learning of image-text pairs (CLIP)."},
]


def arxiv_papers(query: str, top_k: int = 3) -> list[dict]:
    """MOCK 模式下的 arXiv 论文列表（扩散模型主题，真实存在的论文）。"""
    q = (query or "").lower()
    if not q:
        return _MOCK_ARXIV_PAPERS[:top_k]
    tokens = [t for t in re.split(r"\s+", q) if t] + re.findall(r"[一-龥]{2,}", q)

    def score(paper):
        hay = (paper["title"] + paper["snippet"]).lower()
        return sum(1 for t in tokens if t and t.lower() in hay)

    ranked = sorted(_MOCK_ARXIV_PAPERS, key=score, reverse=True)
    hits = [p for p in ranked if score(p) > 0]
    return (hits or _MOCK_ARXIV_PAPERS)[:top_k]


# ---------------- Professor：答疑 ----------------
def professor_answer(message: str, task_title: Optional[str] = None) -> str:
    return (
        f"好问题！我们结合你当前的任务「{task_title or '扩散模型学习'}」来讲。\n\n"
        "**核心直觉**：扩散模型包含两个过程——\n"
        "1. **前向过程**：按固定日程逐步向图片加高斯噪声，经过足够多步后图片近似纯噪声；\n"
        "2. **反向过程**：训练一个神经网络预测每一步加入的噪声，采样时从纯噪声出发逐步"
        "「减去预测噪声」，最终还原出清晰图片。\n\n"
        "训练目标可以理解为一个简单的去噪回归：给模型看加噪图片，让它预测噪声，"
        "预测得越准，反向链就能生成越逼真的样本。\n\n"
        "**检验你的理解**：如果训练时只在中等噪声强度上训练、采样时却从纯噪声开始，"
        "你认为会出现什么问题？想清楚这个，就可以去 Lab 跑通你的第一条推理管线了。"
    )


# ---------------- Lab：实践指导 ----------------
def lab_guidance(task_title: Optional[str] = None) -> dict:
    return {
        "overview": "用 HuggingFace diffusers 以最小代码跑通 Stable Diffusion 文生图，再做参数实验。",
        "steps": [
            {"title": "准备环境",
             "detail": "建议 Python 3.10+、独立虚拟环境；有 NVIDIA GPU 安装 CUDA 版 PyTorch，"
                       "无 GPU 可使用 Colab 或 Apple Silicon 的 MPS 后端。"},
            {"title": "安装依赖",
             "detail": "pip install diffusers transformers accelerate safetensors，"
                       "绘图可选 matplotlib/Pillow。"},
            {"title": "跑通最小管线",
             "detail": "用 DiffusionPipeline.from_pretrained 加载 runwayml/stable-diffusion-v1-5 "
                       "或 stabilityai/stable-diffusion-2-1，输入一句 prompt 调用 pipeline() 出图并保存。"},
            {"title": "参数实验",
             "detail": "固定 prompt，分别改变 num_inference_steps、guidance_scale，"
                       "并尝试 negative_prompt，记录画面变化规律。"},
            {"title": "产出个人作品",
             "detail": "选定主题写 5-10 个结构化 prompt（主体+风格+光影+镜头），"
                       "批量生成并挑选 6-9 张组成作品集。"},
        ],
        "deliverables": ["可复现的文生图脚本/Notebook", "参数对比实验记录", "6-9 张主题作品集"],
        "pitfalls": [
            "首次加载模型需下载数 GB 权重，提前在网络稳定时预下载，避免演示现场等待；",
            "guidance_scale 过高（>15）容易出现过饱和与伪影，常用区间 7-9；",
            "Demo 现场务必准备本地缓存或 mock，避免网络波动导致无法出图。",
        ],
        "tools": ["Python 3.10+", "PyTorch", "HuggingFace diffusers", "transformers", "accelerate"],
    }
