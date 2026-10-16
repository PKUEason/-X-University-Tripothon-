# ZIP 人物模型接入 · 2026-10-15

版本说明：本版包含 2026-10-15 的 ZIP 模型重导及 2026-10-16 的柔和反光材质调整；发布目标与验证见 RELEASE-2026-10-16.md。

## 模型来源：男生从 ZIP 全新重导

按用户要求撤下旧的 `public/assets/student-male.glb`，从《运动人物+模型 男女(1).zip》重新解压男生 FBX 与配套纹理，在空 Blender 场景重新导入。新的运行时文件为 `student-male-zip.glb`，加载路径已切换，避免旧路径缓存。旧运行时文件移至忽略的 `.local/retired-male-before-clean-import/`，不再被网站提供或引用。

10 月 15 日全新重导时移除了男生专用材质补丁；10 月 16 日按用户新要求恢复柔和反光与自然肤色校正，详见下方当前设置。原 ZIP、FBX 和新导出的 GLB 均未修改。

女生仍使用 `student-female.glb`，文件 SHA-256 保持 `8c480863c3569a3c1b68437963d58bc0c83f009e2f76a157b03ee96bb8726ddb`。

## 来源与贴图完整性

完整机器可读报告：`art/character/male-fresh-import-report.json`。

- 原 FBX：`tripo_convert_337953e8-8d94-4e0a-b2fe-d79beac050eb.fbx`
- 原 FBX SHA-256：`d522b4392165151633aa961dea7ae92a5622a8217b870b01fce88881e5682136`
- 新 GLB SHA-256：`a4dfcfa51b43fa2dc45840b42179e5886d923923952a783df5a2f3ce521ccbfa`
- 新 GLB：29,244,748 字节，65 根骨骼。
- 原始 8192×8192 颜色 JPEG 与 4096×4096 法线 JPEG 在 GLB 中逐字节保留，未降采样或重新编码。
- 原始粗糙度/金属度 JPEG 解码后无损打包为 4096×4096 PNG 的 G/B 通道；逐像素对比最大误差均为 0。

保留原生贴图使资产比此前压缩版本大；后续优化应另行验证，不能重新引入颜色损失。

## 动画与场景接入

保留 Walk、Run、Greet、Clap、Dance。ZIP 没有 Idle，静止使用 Greet 开头放松姿势。模型与骨架一并归一化至约 1.78 m；走跑移除平面根位移，校园代码控制移动，播放速度随移动速度调整。

校园和身份预览的骨骼、材质各自独立，几何与纹理共享缓存。保留场景动态光照与色调映射，没有使用无光照材质或自发光提亮。

身份预览补充中性环境反射贴图，使原始金属镜片有可反射的环境；同时降低重复的半球填充光。此为预览灯光设置，不修改人物材质。校园灯光保持原配置。

## 重建命令

```sh
.local/tools/Blender.app/Contents/MacOS/Blender -b --python art/character/import_designer_motion.py -- .local/male-clean-source-20261015 --gender male --native-textures --output-name student-male-zip.glb --report male-fresh-import-report.json
```

## 验证

85 项测试通过，构建通过。测试覆盖来源指纹、内嵌原始贴图、材质与光照回归、骨骼与蒙皮、原始动作、原地循环、加载/卸载和动作状态切换。浏览器检查男生跑步与校园昼夜切换；截图见 `.local/male-fresh-import-preview.jpg`、`.local/male-fresh-import-run.jpg`、`.local/male-fresh-campus-day.jpg`、`.local/male-fresh-campus-night.jpg`。

## 当前材质设置 · 2026-10-16

按用户要求，在新的 `student-male-zip.glb` 上恢复此前较自然的肤色和低灰白反光。仅克隆的男生运行时材质使用 MeshPhysicalMaterial：金属度乘 0.15、环境反射强度 0.4、非金属镜面反射强度 0.15。光照计算前对底色应用 sRGB 饱和度 1.3 和线性 RGB 增益 (1.3, 1.02, 0.83)。保留贴图、法线、粗糙度、动态光照、色调映射及原始动画；自发光仍为零。女生材质和场景灯光不变。

新 GLB SHA-256 仍为 `a4dfcfa51b43fa2dc45840b42179e5886d923923952a783df5a2f3ce521ccbfa`，未换回已撤下的旧资产。

验证：85 项测试和构建通过；浏览器同姿势换光有 20025 个男生像素变化，昼夜切换有 25440 个像素变化，关掉所有灯后人物变黑。女生渲染指标与上一轮一致。校园预览已刷新，页面无错误/警告。截图 `.local/male-soft-reflections-20261016.jpg`、`.local/male-soft-preview-20261016.jpg`。

## 已知限制：原始颜色贴图包含固定光影

2026-10-16 隔离检查确认：仅显示原始颜色贴图、关闭实时灯光/反射/法线计算时，男生仍有头顶亮斑、背部明暗和镜片高光。降低反光与肤色校正不等于去除这些固定光影。本次按用户要求发布当前版本，未执行底色贴图去光照重制。
