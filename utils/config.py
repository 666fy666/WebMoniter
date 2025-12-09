import requests


def get_config():
    try:
        json_url = "https://raw.gitcode.com/qq_35720175/web/raw/main/config.json"
        file = requests.get(json_url)
        return file.json()
    except Exception as e:
        print(e)
        return \
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",

                "Content-Type": "application/x-www-form-urlencoded",

                "push": {
                    "corpid": "wwa721a143a22ceed4",

                    "secret": "OZwYUc5FABoqJVonBioH3DekVeuvlf5pjkxLTdaHJus",

                    "agentid": "1000002",

                    "touser": "FengYu|NiHenPi",

                    "pushplus": "982fe9bccbaf48cca752eb7f5ff1d976",

                    "email": "fy16601750698@163.com"
                },

                "dbs": {
                    "host": "47.103.138.35",

                    "user": "root",

                    "password": "Fy12345678",

                    "db": "spiders"
                },

                "weibo": {
                    "Cookie": "SUB=_2AkMQnjanf8NxqwFRmfAUzW3qaolxzg3EieKmwsd8JRMxHRl-yT8Xqn04tRB6Ox4YSG-X0_kxhElrEHbxRv_Z6Rjk9PTF; SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9W5UK5_uZKE-bGYCxACORG_Z; WBPSESS=fhlE7lUFBip5iXsQIeNCGOaKs3ym2pGNZfaeTaIwCRAWTuEkbZQEftciKu9xqnL4w0i0vejsCaZ2jJqa2qxv8OQvM4Fe33lnAhXprjNUzN7qgFcgepi96waYwobDrqPs",

                    "uid": ["3669102477", "5479678683", "3753348253", "7934944480", "5043186742", "5638314984",
                            "5498336778", "7287985674", "5462283080", "5292770234", "5596164541", "5127297397",
                            "6048569942", "1788775253", "7920554800", "6548060677", "3570167623", "2837256310",
                            "3162343735", "5598574734", "7038749619", "5889340522", "5874514144", "7200526021",
                            "2662534925", "6512991534", "7596025298", "1807623760", "2749401781", "6451935868",
                            "6551834246", "5124933423", "7798421503", "1087413802", "1195354434", "2269438254",
                            "2309864094", "1722647874", "1645677583", "7912061054", "5514146941"],
                    "test":["5127297397"]
                },

                "hy": {
                    "Content-Type": "application/x-www-form-urlencoded",

                    "User-Agent": "Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Mobile Safari/537.36",

                    "Cookie": "__yamid_new=CAB210FCD700000171F81360175A8890; udb_guiddata=5dd684ef4e694be8b073eb6c83e1756d; udb_deviceid=w_829440744201302016; __yamid_tt1=0.771245647717792; sdidshorttest=test; udb_cred=CgARtYlGG1cqlrk5EfyGiFY11dZDMtsORuYBcpvH_2NYJ4wcYYRHW1IuDkdDZysxcoxOfqu9pIPpNAESthrPPXQZ08DbhXfVxGVmcDKVrmUn0sN11KKKrhJfJcsES9kYVp0h9py6EMw-_78IAArZuixu; udb_origin=0; udb_passport=newqq_62aqy37ko; udb_status=1; udb_uid=1704114893; udb_version=1.0; username=newqq_62aqy37ko; yyuid=1704114893; game_did=vwNvSOy5L879-kLpN4FwYrdjIhcHQAyWCz2; alphaValue=0.80; isInLiveRoom=true; guid=0a7d1d59e7bd13664b01eeaceface963; videoBitRate=0; videoLine=6; udb_biztoken=AQAtQqqQ-p8EZwT_aD4d6EmFgUr88-wtCBq7CXehZ4GjeC66jws79xiRzn_gP304hrN4WEmQBjSwPyOR-cda6WN-pzdkLG5fXhs2Ysvsk0jeom5Ar6e7mXt-0TlbsaF7pehptblvRuS9IwjU1TxKOb3gcOXSPb8zbBu2fDJ39xLw5p7Nd1K4uGIru_cvK0Eotb-Q5ukEW0JlevHX4um92LmQDHVipFjZgsm7p3WGSn8jLFku3fpK-RaPkFK59abENDhv6FqYloI7YD7ZTORfSiMprovX2tYukcfmsLwkcbN9Q3ZRIMnYGQsqTkrOK9DRIxnAosVLE3Vr_0-mHjc3DWkk; SoundValue=0.00; Hm_lvt_51700b6c722f5bb4cf39906a596ea41f=1722003652,1722079557,1722140408,1722145343; HMACCOUNT=887991B79248711E; h_unt=1722145344; udb_passdata=3; __yasmid=0.771245647717792; __yaoldyyuid=1704114893; _yasids=__rootsid%3DCAD608F67720000194CB1B0B5E14A860; sdid=0UnHUgv0_qmfD4KAKlwzhqeCoZkBoKCvoP8-K44GZJInfiy3nqxj0JtE9eQ7hu4oWluJe404uQaxxwRVxwEO4lk29iPAyZXVxVtJLO_y4in3WVkn9LtfFJw_Qo4kgKr8OZHDqNnuwg612sGyflFn1dnN7LWrE2iNSENAcZ70sSUAmtPKS9bDxLJfp5mZIKMJm; sdidtest=0UnHUgv0_qmfD4KAKlwzhqeCoZkBoKCvoP8-K44GZJInfiy3nqxj0JtE9eQ7hu4oWluJe404uQaxxwRVxwEO4lk29iPAyZXVxVtJLO_y4in3WVkn9LtfFJw_Qo4kgKr8OZHDqNnuwg612sGyflFn1dnN7LWrE2iNSENAcZ70sSUAmtPKS9bDxLJfp5mZIKMJm; Hm_lpvt_51700b6c722f5bb4cf39906a596ea41f=1722145580; huya_flash_rep_cnt=30; huya_hd_rep_cnt=14; huya_web_rep_cnt=100",

                    "room": ["991108", "333003", "518518", "991222", "321417", "814814", "910004", "528222", "25180653",
                             "143573", "204999", "30511491"]
                },

                "ikuuu":{
                    "url":"https://ikuuu.one/",

                    "X-Requested-With": "XMLHttpRequest",

                    "Accept": "application/json, text/javascript, */*; q=0.01",

                    "Sec-Ch-Ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",

                    "acc":"657769008@qq.com",

                    "pwd":"Fy12345678"

                },

                "douyin":{
                    "url":"http://47.103.138.35",

                    "uid":["MS4wLjABAAAAoumYIHmRPqWY98T5GKDq6TmUZvd2ajc3lgR2axNvM6KRRdSUOSGroY9t9b9w9Wxh","MS4wLjABAAAAWLGVYKNBQ_pz3HYhQ1dRWcywDdgjz5M7fP9nhR9vIh4",
                            "MS4wLjABAAAAHuFui7x3Walw7nu61E_iQgXBU-23twsaX4FGWpb_bmo","MS4wLjABAAAA06y3Ctu8QmuefqvUSU7vr0c_ZQnCqB0eaglgkelLTek",
                            "MS4wLjABAAAA5E8rXhQ_zH31ImQMsUnpPrDfvnPSZf4vKHBa-jDFZN4","MS4wLjABAAAA-CLO5irRNNqoxatfnCz7hV9B7e7QFRff4WG0K3Hs_9k",
                            "MS4wLjABAAAA3S6Z5KzLz3C0S9PdgXNHPnBB96SSVBE00MA8l1NOJf0","MS4wLjABAAAAjW0gMk6HfnozLjpBmla_Ad2igcU4EkqV6WwnkK0ZuNM",
                            "MS4wLjABAAAAR_1bVZNnAY7kcijSSEDAYIkfQYM_JES__DbdGHR5KXeagpCjQD7XqlBIEUkyy4Sb","MS4wLjABAAAApGDzYkvasZVayeWAuJ0ij_-rgJCC-CWdPkNWy00NRiWLrm1RgWWZitck3vAZAH0H",
                            "MS4wLjABAAAAkQtgDTZYCFE82g4_g5Ndt8y_TZ5MuAxOvTkBNR8OUx3jCoV1AKmU07GJ-Tv9FdAl","MS4wLjABAAAAakV4xcvcFuTMT77Zg49CCXPSh9zFQh1Ba26pjEq8XmomjjcO-yA9umMfFS4KtpPS",
                            "MS4wLjABAAAAF0lD0sk09_1YT5iDVrcMf6nENhBdhd_PZwM0-zKgx-M","MS4wLjABAAAApx0rIQNarvIYvECzBBmM_IgJ6A3XBcTi81mrQ7pIkjk",
                            "MS4wLjABAAAAGSCToXHJLbkSaouYNJU68raa3TYVliiEW0tWp2dpNio","MS4wLjABAAAACV5Em110SiusElwKlIpUd-MRSi8rBYyg0NfpPrqZmykHY8wLPQ8O4pv3wPL6A-oz"],

                    "test":["MS4wLjABAAAAHuFui7x3Walw7nu61E_iQgXBU-23twsaX4FGWpb_bmo"]

                },



                "Hot":{
                    "format": "json",

                    "appkey": "8deb6afbef182460e21765bbd7dd761e",

                    "urls": ["https://api.gmya.net/Api/BiliBliHot",
                            "https://api.gmya.net/Api/DouYinHot",
                            "https://api.gmya.net/Api/WeiBoHot"
                            ]
                }

            }
