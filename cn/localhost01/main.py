# -*- coding: utf-8 -*-
import time
from util.str_util import print_msg, send_mail
from spider.taobao_climber import TaobaoClimber
from spider.csdn_downloader import CsdnDownloader
from mail.mail_sender import *
from mail.mail_sender_browser import *
from __init__ import *

if __name__ == '__main__':

    # 1.初始化需要的对象
    climber = TaobaoClimber(taobao_username, taobao_password)
    downloader = CsdnDownloader(csdn_username, csdn_password)
    sender = MailSender(mail_username, mail_authorization_code)
    sender_browser = MailSenderBrowser(mail_username, mail_password, mail_password2)

    # 正则：解析留言内容
    re_note = re.compile(
        ur"^留言:\s*([\w.-]+@[\w.-]+\.\w+)[\s\S]+?((?:https?://)?[-A-Za-z0-9+&@#/%?=~_|!,.;]+[-A-Za-z0-9+&@#/%=~_|])\s*$")
    # 休眠总时间
    sleep_total_time = 0
    # 存在未留言订单
    exists_no_note_order = False

    # 2.1上架宝贝
    climber.shelve()
    is_running = True
    while is_running:
        # 2.2爬取订单
        orders = climber.climb()
        orders_len = len(orders)
        for order in orders:

            if downloader.download_count >= download_total:
                send_mail(sender, message_over_download_total, orders_len)
                is_running = False
                break

            note_array = re.findall(re_note, order[3])
            if len(note_array) != 1:
                if mail_notice_for_no_note:
                    exists_no_note_order = True
                continue

            order_info = "【已产生可操作订单】订单号：%s\t订单日期：%s \t买家：%s\t备注：%s" % order
            print_msg(order_info)

            user_to = note_array[0][0]
            remote_url = note_array[0][1]

            # 2.3下载资源
            local_path = downloader.download(remote_url, local_dir)
            if local_path is None:
                send_mail(sender, message_download_false, order[0])
                continue
            else:
                print_msg("【资源下载成功】本地路径：" + local_path)
            orders_len -= 1

            # 2.4进行下架判断
            if downloader.download_count == download_total - 1:
                if climber.unshelve() is False:
                    send_mail(sender, message_unshelve_false, downloader.download_count)

            # 2.5 发送邮件
            if mail_send_type == 0:
                download_url = server_file_url + os.path.basename(local_path)
                if sender.send(Mail(user_to, download_url)):
                    print_msg("【邮件发送成功】")
                else:
                    send_mail(sender, message_send_false, order[0])
                    continue
            elif mail_send_type == 1:
                if sender.send(Mail(user_to, local_path, 2)):
                    print_msg("【邮件发送成功】")
                else:
                    send_mail(sender, message_send_false, order[0])
                    continue
            else:
                ret = sender_browser.send(user_to, local_path)
                if ret is None:
                    print_msg("【邮件-浏览器-附件发送成功】")
                else:  # 发送失败
                    send_mail(sender, message_send_mail_error, order[0], ret)
                    continue

            # 2.6 订单改为已发货
            if climber.delivered(order[0]) is False:
                send_mail(sender, message_delivered_false, order[0])

        time.sleep(check_order_period)  # 每指定时间抓一次
        sleep_total_time += check_order_period

        if sleep_total_time >= check_refunding_period:  # 每指定时间检查一次退款和未留言订单
            if climber.exists_refunding():
                send_mail(sender, message_exists_refunding)
            if exists_no_note_order:
                send_mail(sender, message_notice_for_no_note)
                exists_no_note_order = False
            sleep_total_time = 0
