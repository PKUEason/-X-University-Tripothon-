# -*- coding: utf-8 -*-
"""Library 文档库：围绕黄金路径主题（扩散模型与文生图）的原创概述文档。

每篇文档结构：
    {"title", "type", "url", "content"}
content 用空行分段，retriever 会按段落切块检索。
扩充语料只需往 LIBRARY_CORPUS 里追加条目，无需改动检索代码。
"""

LIBRARY_CORPUS: list[dict] = [
    {
        "title": "DDPM 论文导读：去噪扩散概率模型",
        "type": "paper",
        "url": "https://arxiv.org/abs/2006.11239",
        "content": (
            "DDPM（Denoising Diffusion Probabilistic Models）是扩散模型的奠基论文，"
            "提出了固定的前向加噪过程与可学习的反向去噪过程。\n\n"
            "前向过程按预先设定的噪声调度（beta schedule），在每一步向图像加入少量高斯噪声，"
            "经过足够多步后图像近似成为纯噪声。这一过程不需要学习，可以直接用闭式公式采样。\n\n"
            "反向过程训练一个神经网络，给定带噪图像和时间步，预测该步加入的噪声。"
            "训练目标就是预测噪声与真实噪声之间的均方误差，本质上是一个逐步去噪的回归任务。\n\n"
            "采样时从纯噪声出发，反复用网络预测噪声并「减去」它，经过上千步迭代还原出清晰图像。"
            "DDPM 证明了这一框架在 CIFAR-10 等数据集上可以生成高质量样本，但原始版本采样很慢。"
        ),
    },
    {
        "title": "潜空间扩散：Stable Diffusion 的核心思想",
        "type": "paper",
        "url": "https://arxiv.org/abs/2112.10752",
        "content": (
            "Latent Diffusion Models（LDM）是 Stable Diffusion 背后的论文，解决的是扩散模型"
            "直接在高分辨率像素空间运行、算力开销过大的问题。\n\n"
            "核心做法是先用一个 VAE（变分自编码器）把图像压缩到低维潜空间：例如 512×512 的图像"
            "被编码为 64×64 的潜表示，数据量缩小几十倍。扩散与去噪过程都在潜空间进行，"
            "最后再用 VAE 解码器把生成的潜表示还原为像素图像。\n\n"
            "文本条件通过预训练的 CLIP 文本编码器注入：文本被编码为嵌入序列，经交叉注意力机制"
            "影响 U-Net 的去噪过程，从而实现文本到图像（文生图）生成。\n\n"
            "由于把最耗算力的扩散过程移到了压缩空间，LDM 可以在单张消费级 GPU 上运行，"
            "这是 Stable Diffusion 得以普及的关键原因。"
        ),
    },
    {
        "title": "Score-Based 生成模型与随机微分方程",
        "type": "paper",
        "url": "https://arxiv.org/abs/2011.13456",
        "content": (
            "Score-Based Generative Modeling through SDEs 用随机微分方程统一了扩散模型与"
            "score-based 生成模型的理论框架。\n\n"
            "Score 指数据分布的对数概率密度梯度，指向「概率增大的方向」。模型学习每个噪声尺度下"
            "的 score 函数后，就可以沿概率梯度把噪声样本逐步引导回数据分布。\n\n"
            "论文指出前向加噪可以用一个连续时间的 SDE 描述，而反向过程对应一个数学上可推导的"
            "反向 SDE；求解反向 SDE 即可生成样本。DDPM 可以看作这一连续框架的离散特例。\n\n"
            "该框架还支持概率流 ODE：一条确定性的采样路径，在相同起点下得到与随机采样一致的结果，"
            "并使精确的似然计算和潜空间编辑成为可能。"
        ),
    },
    {
        "title": "扩散模型入门长文：从直觉到数学",
        "type": "article",
        "url": "https://lilianweng.github.io/posts/2021-07-11-diffusion-models/",
        "content": (
            "Lilian Weng 的《What are Diffusion Models?》是流传最广的扩散模型入门长文，"
            "把直觉、公式和训练流程串在一起讲解。\n\n"
            "文章从前向加噪的重参数化技巧讲起：任意一步的带噪图像都可以由原图和噪声直接采样，"
            "训练时不需要真的逐步加噪，这大幅简化了实现。\n\n"
            "随后推导反向过程的目标函数，说明预测噪声的网络为什么等价于在学习数据分布的 score，"
            "并梳理了噪声调度、训练稳定性与采样加速（如 DDIM）等工程细节。\n\n"
            "适合作为读完 DDPM 原文前后的辅助材料：先建立整体图景，再回到论文细节。"
        ),
    },
    {
        "title": "HuggingFace Diffusers 实践文档",
        "type": "tool",
        "url": "https://huggingface.co/docs/diffusers",
        "content": (
            "Diffusers 是 HuggingFace 提供的扩散模型工具库，封装了推理管线、训练脚本和"
            "大量预训练模型，是跑通文生图 Demo 最常用的工程入口。\n\n"
            "核心抽象 DiffusionPipeline 把分词器、文本编码器、U-Net、调度器和 VAE 组装在一起："
            "几行代码加载 Stable Diffusion 检查点，传入文本提示即可生成图像。\n\n"
            "调度器（scheduler）可以灵活替换：DDPM 步数多但慢，DDIM、DPM-Solver、Euler 等"
            "调度器能用二三十步甚至更少完成采样，显著缩短出图时间。\n\n"
            "文档还覆盖 LoRA 微调、ControlNet 条件控制、图像到图像转换等任务，并给出"
            "CPU / GPU / Apple Silicon 不同后端的配置方式。"
        ),
    },
    {
        "title": "U-Net：扩散模型的去噪网络",
        "type": "article",
        "url": "https://en.wikipedia.org/wiki/U-Net",
        "content": (
            "U-Net 是扩散模型中负责预测噪声的主干网络，最初为医学图像分割设计，"
            "因其编码器—解码器的对称结构形似字母 U 而得名。\n\n"
            "下采样路径逐步压缩空间分辨率、提取语义；上采样路径逐步恢复分辨率，"
            "并通过跳跃连接把高分辨率细节直接传递给解码器，兼顾全局语义与局部细节。\n\n"
            "在文生图模型里，U-Net 的输入是带噪潜表示和时间步嵌入，文本条件通过交叉注意力层"
            "注入：文本嵌入作为键和值，图像特征作为查询，使去噪结果服从文本描述。\n\n"
            "时间步嵌入让同一个网络可以处理所有噪声强度：网络根据当前处于加噪链的哪个位置，"
            "调整自己的预测行为。"
        ),
    },
    {
        "title": "CLIP 文本编码器与提示词（Prompt）",
        "type": "article",
        "url": "https://openai.com/index/clip/",
        "content": (
            "CLIP 是用大规模图文对比学习训练的模型，包含一个图像编码器和一个文本编码器，"
            "能把图像和文本映射到同一个语义空间。\n\n"
            "Stable Diffusion 使用 CLIP 的文本编码器把用户提示词转换为嵌入序列，"
            "再经交叉注意力引导 U-Net 去噪，这是文本能够控制生成内容的桥梁。\n\n"
            "提示词工程因此重要：具体的主体、风格、画质描述（如「电影感光影」「高细节」）"
            "能显著改善结果；负面提示词（negative prompt）用于排除不想要的元素。\n\n"
            "需要注意 CLIP 文本编码器通常有 77 个 token 的长度限制，过长的提示会被截断，"
            "工程上常对超长文本做分块编码后拼接。"
        ),
    },
    {
        "title": "噪声调度与 DDIM 快速采样",
        "type": "paper",
        "url": "https://arxiv.org/abs/2010.02502",
        "content": (
            "噪声调度（noise schedule）决定每一步加入噪声的多少，常见形式有线性、余弦（cosine）"
            "等，直接影响生成质量与训练稳定性。\n\n"
            "DDIM（Denoising Diffusion Implicit Models）在不重新训练模型的前提下，"
            "把采样步数从 DDPM 的上千步压缩到几十步，解决原始 DDPM 采样慢的问题。\n\n"
            "关键思想是 DDPM 的训练只约束每一步的边缘分布，并未固定采样路径；DDIM 构造了一条"
            "非马尔可夫的确定性路径，在时间步上「跳着走」也能保持样本质量。\n\n"
            "确定性采样还带来可复现性：固定随机种子和提示词，每次生成相同图像，"
            "这对调试和演示视频录制很有用。现代调度器如 DPM-Solver、Euler 进一步减少了步数。"
        ),
    },
    {
        "title": "LoRA：低成本微调扩散模型",
        "type": "article",
        "url": "https://huggingface.co/docs/diffusers/training/lora",
        "content": (
            "LoRA（Low-Rank Adaptation，低秩适配）是一种参数高效的微调方法，"
            "让用户用少量图片和显存就能让扩散模型学会新风格或新主体。\n\n"
            "做法是冻结原始模型权重，只在注意力等层旁边插入很小的低秩矩阵进行训练，"
            "可训练参数量通常不到原模型的百分之一，训练快、存储小。\n\n"
            "训练好的 LoRA 权重只有几十到几百 MB，可以按需加载、叠加或卸载，"
            "社区因此能方便地分享各种风格与角色适配。\n\n"
            "推理时通过提示词中的触发词唤起 LoRA 效果。相比全量微调，LoRA 更不容易"
            "过拟合，也便于在同一基础模型上管理多个定制能力。"
        ),
    },
    {
        "title": "生成图像的评估：FID 与 CLIP Score",
        "type": "article",
        "url": "https://en.wikipedia.org/wiki/Fr%C3%A9chet_inception_distance",
        "content": (
            "评估生成图像主要有两类维度：图像是否逼真、是否符合文本条件。\n\n"
            "FID（Fréchet Inception Distance）用预训练网络提取真实图像与生成图像的特征，"
            "比较两组特征分布的距离；FID 越低表示生成分布越接近真实分布，是最常用的整体质量指标。\n\n"
            "CLIP Score 计算生成图像与输入文本在 CLIP 语义空间中的相似度，"
            "衡量文生图结果与提示词的对齐程度，分数越高表示越「听话」。\n\n"
            "实践中还要结合人工检查：指标可能掩盖伪影、多样性不足或概念性错误。"
            "对 Demo 而言，固定若干提示词做对比生成、观察稳定性，往往比单一指标更直观。"
        ),
    },
]
