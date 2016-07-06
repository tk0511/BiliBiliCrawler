#-*- coding:utf-8 -*-

import re
import os
import json
import time
import gzip
import Queue
import pickle
import codecs
import thread
import urllib2
import multiprocessing
from bs4 import BeautifulSoup
from StringIO import StringIO
from collections import namedtuple

DATA = []
MISS = []
TIMER = 0.0


AID_URL_MODLE = 'http://api.bilibili.com/x/stat?aid=%s'
ANIME_URL_MODLE = 'http://bangumi.bilibili.com/anime/%s'
SPONSOR_URL_MODLE = 'http://bangumi.bilibili.com/sponsor/rankweb/get_sponsor_total?season_id=%s&page=1&pagesize=0'

AID_REGEX = re.compile('aid ?=[^0-9]*([0-9]*)')
TOTAL_COINS_REGEX = re.compile('<span id="icon_count">([^<]*)')

CrawerJob = namedtuple('CrawerJob', 'season_id url')
SubThreadJob = namedtuple('SubThreadJob', 'season_id index name url')
Episode = namedtuple('Episode', 'season_id index name tag play fav share reply coins danmaku his_rank')
Anime = namedtuple('Anime', 'season_id name date status tag total_play total_fans total_danmaku total_coins total_sponsor detail')

def main():
    max_fail = 300
    max_season_id = 7000
    season_id = 0
    fail_counter = 0
    sub_crawer_qty = 12
    job_in_progress = []

    sub_crawer_list = []
    lock = multiprocessing.Lock()
    crawer_jobs = multiprocessing.Queue()
    crawer_results = multiprocessing.Queue()

    for _ in range(sub_crawer_qty):
        process = multiprocessing.Process(target = sub_crawer, args = (crawer_jobs, crawer_results, lock))
        sub_crawer_list.append(process)
        process.start()

    # Run
    while season_id < max_season_id and fail_counter < max_fail:
        while crawer_jobs.qsize() < 300 and season_id < max_season_id:
            crawer_jobs.put(create_job(season_id))
            job_in_progress.append(season_id)
            season_id += 1
            if season_id % 300 == 0:
                print('Crawing: ' + str(season_id - crawer_jobs.qsize()) + ' : ' + str(season_id))
            
        while crawer_jobs.qsize() > 50:
            if crawer_results.qsize() > 0:
                record = crawer_results.get()
                if good_record(record):
                    DATA.append(record)
                    fail_counter = 0
                else:
                    fail_counter += 1
                job_in_progress.remove(record.season_id)
            else:
                time.sleep(0.1)
                break

    while len(job_in_progress) > 0:
        if crawer_results.qsize() > 0:
            record = crawer_results.get()
            if good_record(record):
                DATA.append(record)
            job_in_progress.remove(record.season_id)
        else:
            time.sleep(10)
            print('Crawing: ' + str(season_id - crawer_jobs.qsize()) + ' : ' + str(season_id))
            print(str(job_in_progress))

    DATA.sort()

    # Kill sub process
    for _ in sub_crawer_list:
        crawer_jobs.put(ending_signal_P())
    while crawer_results.qsize() != sub_crawer_qty:
        time.sleep(0.1)
    for p in sub_crawer_list:
        p.terminate()

def sub_crawer(job_queue, result_queue, lock):
    sub_thread_qty = 13
    sub_thread_job_queue, sub_thread_result_queue = create_sub_thread(sub_thread_qty, episode_crawer)
    while job_queue.qsize() >= 0:
        time.sleep(0.1)
        while job_queue.qsize() > 0:
            job = job_queue.get()
            if job.season_id >= 0 :
                try:
                    soup = BeautifulSoup(get(job.url), 'lxml')
                    result = get_anime_info(job.season_id, soup)
                except:
                    result_queue.put(Anime(job.season_id, *none_tuple(10)))
                    continue

                map(sub_thread_job_queue.put, creatr_sub_thread_jobs(job.season_id, soup))
                sub_thread_job_queue.join()

                while sub_thread_result_queue.qsize() > 0:
                    result[-1].append(sub_thread_result_queue.get())
                result_queue.put(Anime(*result))
            else:
                for _ in range(sub_thread_qty):
                    sub_thread_job_queue.put(ending_signal_T())
                sub_thread_job_queue.join()
                result_queue.put(str(os.getpid()) + ' done')
                return None

def create_sub_thread(n, worker):
    in_queue = Queue.Queue()
    out_queue = Queue.Queue()
    for _ in range(n):
        thread.start_new_thread(worker, (in_queue, out_queue))
    return (in_queue, out_queue)

def episode_crawer(job_queue, result_queue):
    while job_queue.qsize() >= 0:
        time.sleep(0.1)
        while job_queue.qsize() > 0 :
            job = job_queue.get()
            if job.season_id >= 0:
                result_queue.put(get_episode_info(job.season_id,job.index, job.name, job.url))
                job_queue.task_done()
            else:
                job_queue.task_done()
                return None

def creatr_sub_thread_jobs(season_id, soup):
    jobs = []
    for soup_obj in soup.find_all('a', 'v1-long-text'):
        try:
            jobs.append(SubThreadJob(season_id, len(jobs) + 1, soup_obj.contents[2].encode('utf8'), soup_obj.attrs['href']))
        except:
            jobs.append(SubThreadJob(season_id, len(jobs) + 1, '', soup_obj.attrs['href']))
    return tuple(jobs)

def ending_signal_P():
    return CrawerJob(-1, ())

def ending_signal_T():
    return SubThreadJob(-1, *none_tuple(3))

def get_episode_info(season_id, index, name, url):
    try:
        info = json.loads(get(AID_URL_MODLE % AID_REGEX.search(get(url),17000).group(1)))['data']
    except:
        return Episode(season_id, index, *none_tuple(9))

    return Episode(season_id,
                   index,
                   name,
                   None,
                   info['in_play'],
                   info['fav'],
                   info['share'],
                   info['reply'],
                   info['coin'],
                   info['dm'],
                   info['his_rank']
                   )

def get_anime_info(season_id, soup):
    try:
        total_coins = my_to_int(TOTAL_COINS_REGEX.search(get(soup.find('a', 'v1-long-text').attrs['href']),16000).group(1))
    except:
        total_coins = None

    return Anime(
        season_id,
        soup.find('h1','info-title').attrs['title'].encode('utf8'),
        soup.find('div','info-update').contents[1].contents[1].next.encode('utf8'),
        soup.find('div','info-update').contents[1].contents[3].next.encode('utf8'),
        tuple(map(lambda x:x.contents[0].encode('utf8'),soup.find_all('span','info-style-item'))),
        my_to_int(soup.find('span','info-count-item-play').contents[3].contents[0].encode('utf8')),
        my_to_int(soup.find('span','info-count-item-fans').contents[3].contents[0].encode('utf8')),
        my_to_int(soup.find('span','info-count-item-review').contents[3].contents[0].encode('utf8')),
        total_coins,
        json.loads(get(SPONSOR_URL_MODLE % season_id))['result']['users'],
        []
        )

def create_job(season_id):
    return CrawerJob(season_id, ANIME_URL_MODLE % season_id)

def get(url):
    try:
        response = urllib2.urlopen(url, timeout=3)
    except:
        response = urllib2.urlopen(url, timeout=3)

    if response.info().get('Content-Encoding') == 'gzip':
        buf = StringIO(response.read())
        try:
            f = gzip.GzipFile(fileobj=buf)
            data = f.read()
        except:
            data = f.extrabuf
    else:
        data = response.read()
    response.close()
    return data

def none_tuple(x):
    return tuple(None for _ in range(x))

def my_to_int(str):
    if ord(str[-1]) & 0b10000000:
        return int(float(str[:-3]) * 10000)
    else:
        return int(str)

def good_record(record):
    if record.name == None:
        return False
    record.detail.sort()
    for episode in record.detail:
        if episode.name == None:
            MISS.append('Miss: ' + str(record.season_id) + ' | "' + record.name + '" | ' + str(episode.index))
    return True

def to_str(l,r):
    if type(l) == str:
        if len(l) > 0:
            left = l
        else:
            left = ''
    elif type(l) == list or type(l) == tuple:
        if len(l) == 0:
            left = ''
        elif len(l) == 1:
            left = str(l[0])
        else:
            left = '"' + reduce(lambda x,y:str(x)+','+str(y),l) + '"'
    else:
        left = str(l)
    if type(r) == str:
        if len(r) > 0:
            right = '"' + r + '"'
        else:
            right = ''
    elif type(r) == list or type(r) == tuple:
        if len(r) == 0:
            right = ''
        elif len(r) == 1:
            right = str(r[0])
        else:
            right = '"' + reduce(lambda x,y:str(x)+','+str(y),r) + '"'
    else:
        right = str(r)
    return left + '|' + right


#Run
if __name__=='__main__':
    multiprocessing.freeze_support()
    TIMER = time.time()

    main()

    for msg in MISS:
        print(msg.decode('utf8'))
    print('-------------------------------------------')
    print('Time used: ' + str(time.time() - TIMER))
    print('Total miss: ' + str(len(MISS)))
    print('Anime crawed: ' + str(len(DATA)))
    print("<<< Saving, don't close!")

    #SAVE DATA
    with open('anime_data.pickle', 'wb') as f:
        pickle.dump(DATA, f)
        f.close()
    
    with codecs.open('missed_craw.txt', 'w', 'utf_8_sig') as f:
        for miss in MISS:
            f.write(unicode(miss + '\n', "utf-8"))
        f.close()

    with codecs.open('anime_data.txt', 'w', 'utf_8_sig') as af:
        with codecs.open('episode_data.txt', 'w', 'utf_8_sig') as ef:
            for anime in DATA:
                af.write(unicode(reduce(to_str, anime[:-1]) + '\n', "utf-8"))
                for episode in anime[-1]:
                    ef.write(unicode(reduce(to_str, episode) + '\n', "utf-8"))
            ef.close()
        af.close()

    print('Done')
    os.system('pause')

'''
with open('anime_data.pickle', 'rb') as f:
    DATA = pickle.load(f)
    f.close()
'''