# BiliBiliCrawler

爬虫一枚，抓取BiliBili上所有动漫番剧的信息。

###使用说明
>抓取的数据保存在全局变量DATA中，运行完毕后会自动将数据保存为二进制和utf-8格式。
>
>二进制文件可用pickle读取，文件名为anime\_data.pickle。
>
>文本文件分别保存番剧信息和集信息至anime\_data.txt和episode_data.txt中。

>跑完一圈大约15分钟。

#####DATA数据结构
>######DATA[...]
>例：DATA[0] = 抓取的第一部番的信息

>namedtuple('Anime', 'season_id name date status tag total_play total_fans total_danmaku total_coins total_sponsor detail')

>namedtuple（番号，番名，开播日期，连载状态，标签，总播放，总追番，总弹幕，总硬币，总承包，[...]）

>#####DATA[...].detail[...]
>例：DATA[0].detail[1] = 抓取的第一部番的第二集的信息

>namedtuple('Episode', 'season_id index name tag play fav share reply coins danmaku his_rank')

>namedtuple(番号，集号，集名，标签，播放数，收藏数，分享数，回复数，硬币数，弹幕数，历史最高排名）

#####文本文件结构
>数据以 | 符号分隔，字符串以 " 符号包裹，换行符分行

>######anime\_data.txt
>番号|番名|开播日期|连载状态|标签|总播放|总追番|总弹幕|总硬币|总承包

>######episode_data.txt
>番号|集号|集名|标签|播放数|收藏数|分享数|回复数|硬币数|弹幕数|历史最高排名

#####调整
>修改main()函数下的sub\_crawer\_qty调整进程数。
>
>修改sub\_crawer()函数下的sub\_thread\_qty调整每条进程下的线程数。
