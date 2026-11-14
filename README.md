# 福外课表自动抓取 + iPhone 同步

福州外语外贸学院（jw.fzfu.edu.cn 正方教务）课表爬虫：每日定时抓取 → 生成标准
**iCalendar (.ics)** → iPhone 日历/课表 App 自动同步。**手机端零广告**。

## 项目结构

| 文件 | 作用 |
|---|---|
| `login.py` | 教务登录（RSA PKCS#1 v1.5 加密密码，自动取 csrftoken/公钥，无验证码） |
| `kebiao.py` | 主脚本：自动检测当前学期 → 抓课表/节次/周映射 → 生成 `kebiao.ics` + `kebiao.json` |
| `serve.py` | 局域网 HTTP 服务（可选）：把 ics 暴露给 iPhone 订阅 |
| `.github/workflows/kebiao.yml` | GitHub Actions 每日 06:00（北京时间）自动抓取并发布 |
| `secret.txt` | 本地凭据文件（第一行学号，第二行密码），**已被 .gitignore 排除** |

## 本地运行

```bash
# 方式1: 命令行传参
python kebiao.py 你的学号 "你的密码"

# 方式2: secret.txt (第一行学号, 第二行密码)
python kebiao.py
```

输出：
- `kebiao.ics` — 全学期课表（184 条课次/学期，按课次逐周展开，UID 稳定可增量更新）
- `kebiao.json` — 结构化数据（课程/教师/场地/周次/节次）

---

## 方案 A（推荐）：GitHub Actions 每日自动抓取 → iPhone 日历订阅（全自动、无广告）

1. 新建 GitHub 仓库（如 `fzfu-kebiao`，Public 或 Private + Pages 都行），把
   本目录的 `login.py`、`kebiao.py`、`.github/`、`.gitignore` 推上去
   （**不要推 secret.txt**）。
2. 仓库 Settings → Secrets and variables → Actions → 新建两个 Secret：
   - `KEBIAO_USER` = 学号
   - `KEBIAO_PASS` = 密码
3. Settings → Pages → Branch 选 `gh-pages`（Actions 首次跑完后自动生成）。
4. 手动触发一次：Actions → 福外课表日报 → Run workflow。
5. 完成后订阅地址（用户名/仓库名换成你的）：
   ```
   https://<你的用户名>.github.io/<仓库名>/kebiao.ics
   ```
6. iPhone：**设置 → 日历 → 账户 → 添加已订阅的日历 → 粘贴 URL**。
   iOS 日历会自动每日刷新（可手动下拉刷新），从此**全自动、零广告**。

> 课表变更（调课/新增）会在次日 06:00 自动更新；UID 稳定，同一节课不会重复显示。

---

## 方案 B：Windows 本机定时（电脑需开机）

```powershell
# 注册每日 06:05 自动任务（python 绝对路径按实际环境改）
schtasks /Create /TN "FZFU Kebiao" /SC DAILY /ST 06:05 /F `
  /TR "\"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe\" \"D:\DSH_Wrodkstation\fzfu_kebiao\kebiao.py\""

schtasks /Run /TN "FZFU Kebiao"   # 立即跑一次验证
```

后续把生成好的 `kebiao.ics` 分享到 iPhone（AirDrop / 文件 App），或用 WebDAV/网盘同步。
局域网内也可以直接订阅（电脑需开机）：
```powershell
python serve.py          # 监听 8090 端口
```
iPhone 订阅 `http://<电脑局域网IP>:8090/kebiao.ics`；需外网访问就套 Tailscale/ngrok。

---

## 方案 C：iOS 快捷指令（可选增强）

订阅日历已经是自动的。想再要一个"手动更新/提醒"捷径：

1. 快捷指令 App → 自动化 → 创建个人自动化 → 每天 07:10（或上课前）。
2. 操作：**获取 URL 内容**（填 `https://<用户名>.github.io/<仓库名>/kebiao.ics`）
   → **存储到文件**（iCloud Drive/课表/）→ **显示通知**「今日课表已同步」。
3. 也可用「快捷指令 → 浏览器打开订阅 URL」一键在日历里手动刷新。

若用 GitHub 方案，还有更彻底的"一键立即重抓"思路：仓库 Actions 页点
**Run workflow** 即可（手机浏览器也能操作）。

---

## iPhone 端课表 App 推荐（无广告）

| App | 广告 | 说明 |
|---|---|---|
| **系统日历（订阅）** | ✅ 零广告 | 方案 A 直接订阅，最省事，自动同步 |
| **iStudiez Pro** | ✅ 零广告（¥68 买断） | 最强课表管理：支持 iCal 订阅/导入、作业、成绩、提醒，一次买断无内购 |
| **WakeUp 课表** | 免费版有广告，可内购去除 | 支持 URL/iCal 订阅、教务导入（正方可直连）、桌面小组件；开源版无广告（需自签） |
| 超级课程表 / 课程格子 | 广告多 | 支持正方教务自动导入，但广告/推广较重，不推荐 |

**首选组合**：系统日历订阅（方案 A）+ iStudiez Pro 或 WakeUp 课表（同样的 URL 再订阅一份，用于看周次/教室详情）。

---

## 常见问题

- **改了密码** → 更新 `KEBIAO_PASS` Secret（或 secret.txt），下次自动抓取生效。
- **课程表为空** → 学期初教务未排课或未开放查询；脚本自动跟随当前学期。
- **单双周课程** → 已正确解析 `1-16周(单)/(双)` 等格式。
- **节假日** → 教务原样返回，元旦/法定假日当天可能仍显示排课，以学校通知为准。
- **误报异地登录** → GitHub Actions 的 IP 会变，正方只记录不拦截；介意的话改用方案 B（本机 IP）。