---
name: browser-publish-control
description: 在明确指定的本机浏览器页面上核验账号并准备稿件，支持文字、文件、点击和经确认的最终提交。
---

# 网页发布控制
用scripts/browser.py接入已授权本机CDP浏览器。须明确页面URL与唯一account-selector，不默认选择第一标签页；账号文字必须与实例登记的实际可见ID一致。
observe保存页面截图和DOM哈希；每次填写、上传、点击都用真实当前selector与expected-dom，之后重新observe。编辑只允许reviewed阶段且需设备锁。
submit必须当前用户确认、台账publishing及一次attempt。点击结果不代表成功，后续核验后台作品ID、状态和账号再complete/uncertain。
不要自动读取或导出登录Cookie。没有CDP/Playwright时使用宿主实际浏览器工具按相同流程；无法接入则说明，不能虚报已经上传。
