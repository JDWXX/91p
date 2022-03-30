import datetime
import os
import shutil

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import redis
# import socks
from telethon import TelegramClient, events
from urllib import parse
import util
from pyp import page91

captionTemplate = '''标题: %s
收藏: %s
作者: %s
关键词： %s
'''
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))
REDIS_PASS = os.getenv('REDIS_PASS')
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))
bot = TelegramClient(None, API_ID, API_HASH,
                     # proxy=(socks.HTTP, '127.0.0.1', 10809)
                     ).start(
    bot_token=BOT_TOKEN)
redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASS, db=1, decode_responses=True)


async def saveToredis(key, message_id, user_id):
    redis_conn.set(key, str(message_id) + ',' + str(user_id))


async def getFromredis(key):
    get = redis_conn.get(key)
    if get is not None:
        messList = get.split(',')
        return int(messList[0]), int(messList[1])
    else:
        return 0, 0


@bot.on(events.NewMessage(pattern='/start'))
async def send_welcome(event):
    await event.client.send_message(event.chat_id, '向我发送91视频链接，获取视频,有问题请留言 @bzhzq')


@bot.on(events.NewMessage(pattern='/get91home'))
async def send_welcome(event):
    await event.client.send_message(event.chat_id, '免翻地址: ' + await page91.get91Home())


@bot.on(events.NewMessage(pattern='/help'))
async def send_welcome(event):
    await event.client.send_message(event.chat_id, '''常见问题:
         1.如何设置用户名?

           点击头像设置.

         2.我发送的链接后,没收到视频

           部分高清视频刚发布后还在转码，大概在视频发布时间一小时后再尝试发送链接下载.  

''')



@bot.on(events.NewMessage)
async def echo_all(event):
    text = event.text

    if 'viewkey' in text:  # 处理91的视频
        sender = await event.get_sender()

        if sender.username is None:
            await event.client.send_message(event.chat_id, '请设置用户名后再发送链接')
            return
        print("消息来自:" + str(sender.username), ":", event.text)
        params = parse.parse_qs(parse.urlparse(text).query)
        viewkey = params['viewkey'][0]
        viewkey_url = 'https://91porn.com/view_video.php?viewkey=' + viewkey

        # redis查询历史数据
        mid, uid = await getFromredis(viewkey)
        try:
            await event.client.forward_messages(event.chat_id, mid, uid)
            return
        except:
            print("消息已被删除或不存在，无法转发")
        videoinfo = await page91.getVideoInfo91(viewkey_url)
        await event.client.send_message(event.chat_id,
                                        '真实视频地址:' + videoinfo.realM3u8 + ' ,正在下载中... ,请不要一次性发送大量链接,被发现后会被封禁! ! !')
        title = videoinfo.title
        if '.mp4' in videoinfo.realM3u8:
            await  util.run(videoinfo.realM3u8, viewkey)
        else:
            await util.download91(videoinfo.realM3u8, viewkey)

        # 截图
        await util.imgCover(videoinfo.imgUrl, viewkey + '/' + viewkey + '.jpg')
        segstr = await util.seg(title)
        msg = await event.reply(
            '视频下载完成，正在上传。。。如果长时间没收到视频，请重新发送链接')

        # 发送视频
        message = await event.client.send_file(event.chat_id,

                                               viewkey + '/' + viewkey + '.mp4',
                                               supports_streaming=True,
                                               thumb=viewkey + '/' + viewkey + '.jpg',
                                               caption=captionTemplate % (
                                                   title, videoinfo.scCount, '#' + videoinfo.author, segstr),
                                               reply_to=event.id,
                                               )
        await msg.delete()
        await saveToredis(viewkey, message.id, message.peer_id.user_id)
        shutil.rmtree(viewkey)
        print(str(datetime.datetime.now()) + ':' + title + ' 发送成功')

    elif 'hsex.men/video-' in text: #补充,不向redis存了
        sender = await event.get_sender()
        if sender.username is None:
            await event.client.send_message(event.chat_id, '请设置用户名后再发送链接')
            return
        p=parse.urlparse(text)
        viewkey= p.path.replace('/','')
        print("消息来自:" + str(sender.username), ":",text)
        videoInfo=await page91.getHs(text)
        await util.download91(videoInfo.realM3u8, viewkey)

        # 截图
        await util.imgCover(videoInfo.imgUrl, viewkey + '/' + viewkey + '.jpg')
        segstr = await util.seg(videoInfo.title)
        msg = await event.reply(
            '视频下载完成，正在上传。。。如果长时间没收到视频，请重新发送链接')
        # 发送视频
        await event.client.send_file(event.chat_id,
                                               viewkey + '/' + viewkey + '.mp4',
                                               supports_streaming=True,
                                               thumb=viewkey + '/' + viewkey + '.jpg',
                                               caption=captionTemplate % (
                                                   videoInfo.title,'000', '#' + videoInfo.author, segstr),
                                               reply_to=event.id,
                                               )
        await msg.delete()
        shutil.rmtree(viewkey)
        print(str(datetime.datetime.now()) + ':' + videoInfo.title + ' 发送成功')

# 首页视频下载发送
async def page91DownIndex():
    urls = await page91.page91Index()
    print(urls)
    for url in urls:
        params = parse.parse_qs(parse.urlparse(url).query)
        viewkey = params['viewkey'][0]
        # redis查询历史数据
        mid, uid = await getFromredis(viewkey)
        if uid != 0:
            print('消息存在')
            try:
                await bot.forward_messages(GROUP_ID, mid, uid)
                continue
            except:
                print('消息转发失败:', url)
        else:
            print("消息不存在，无法转发")
        videoinfo = await page91.getVideoInfo91(url)
        # await bot.send_message(GROUP_ID, '真实视频地址:' + videoinfo.realM3u8)
        title = videoinfo.title

        try:
            # 下载视频
            await util.download91(videoinfo.realM3u8, viewkey)
        except:
            print('转码失败')
            return

        # 截图
        await util.imgCover(videoinfo.imgUrl, viewkey + '/' + viewkey + '.jpg')
        segstr = await util.seg(title)
        # 发送视频

        message = await bot.send_file(GROUP_ID,
                                      viewkey + '/' + viewkey + '.mp4',
                                      supports_streaming=True,
                                      thumb=viewkey + '/' + viewkey + '.jpg',
                                      caption=captionTemplate % (
                                          title, videoinfo.scCount, '#' + videoinfo.author, segstr),
                                      )
        try:
            fid = message.peer_id.channel_id
        except:
            fid = message.peer_id.user_id
        await saveToredis(viewkey, message.id, fid)
        shutil.rmtree(viewkey)


scheduler = AsyncIOScheduler()
scheduler.add_job(page91DownIndex, 'cron', hour=6, minute=50)
scheduler.start()
print('开启定时任务!!!')
bot.run_until_disconnected()
