# lin-router

本地可视化中转代理，适合 Hermes 接入。

## 启动

```bash
python app.py
```

默认固定端口：

```text
http://127.0.0.1:18400
```

Hermes 里填 OpenAI 兼容地址：

```text
http://127.0.0.1:18400/v1
```

## 配置方式

1. 先建连接组：填写 `Base URL` 和 `Ark API Key`
2. 再建模型：只填写模型名称、EP ID，并选择连接组
3. 多个模型可以复用同一个连接组，不需要重复填写 key

## 能力

- 当前模型额度耗尽后自动切换下一个可用模型
- 端口固定为较少占用的 `18400`
- 支持 `/v1/chat/completions` 兼容转发
