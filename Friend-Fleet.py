# pymongo需要3版本，4不行
import pymongo
import requests
import json
import copy
import os

MapareaId = int(input("请输入海域ID，然后回车："))
KCClient = pymongo.MongoClient("47.106.254.135", 9018)[
    "kcwiki-development"]["friendlyrecords"]
AllShips = json.loads(requests.get(
    "http://kcwikizh.github.io/kcdata/ship/all.json").content)
AllEquipments = json.loads(requests.get(
    "http://kcwikizh.github.io/kcdata/slotitem/all.json").content)


def FoundShipDetails(id, key):
    for i in AllShips:
        if(i['id'] == id):
            return i[key]


def FoundEquipmentDetails(id, key):
    for i in AllEquipments:
        if(i['id'] == id):
            return i[key]


# RemovingRedundant为查询数据库所有的友军到达点（包括错误记录），格式为[E几mapinfo_no，路径curCellId]
RemovingRedundant = []
for i in KCClient.find({"maparea_id": MapareaId}, {"mapinfo_no": 1, "curCellId": 1}):
    TempArray = [i['mapinfo_no'], i['curCellId']]
    try:
        RemovingRedundant.index(TempArray)
    except:
        RemovingRedundant.append(TempArray)

# 通过查询api_ship_id字段是否为空来去除是否为错误记录
RemovingFaults = []
for Index, i in enumerate(RemovingRedundant):
    print('路径点去重：{}/{}'.format(Index+1, len(RemovingRedundant)))
    IsEmpty = KCClient.find({"$and": [{"maparea_id": MapareaId}, {"mapinfo_no": i[0]}, {
                            "curCellId": i[1]}, {"api_ship_id": {"$ne": []}}]}).limit(1)
    if(list(IsEmpty) != []):
        RemovingFaults.append(i)

# RealPoint为归纳同一个点的不同路径，格式为[E几mapinfo_no，路径点，[路径curCellId,路径curCellId...]]
# 此处利用了kcnav（https://tsunkit.net/nav/）的api，第一次使用，稳定性尚需确认
# 网址https://tsunkit.net/api/routing/maps/53-5的route即路径点的信息，格式为{路径:[出发点,到达点,？,？],...}
RealPoint = []
TempPoints = []
TempPoint = []
for i in RemovingFaults:
    Route = json.loads(requests.get(
        'https://tsunkit.net/api/routing/maps/{}-{}'.format(MapareaId, i[0])).content)["route"]
    Points = [i[0], Route[str(i[1])][1]]
    try:
        index = TempPoints.index(Points)
        RealPoint[index][2].append(i[1])
    except:
        TempPoints.append(Points)
        TempPoint = copy.deepcopy(Points)
        TempPoint.append([i[1]])
        RealPoint.append(TempPoint)

# 填充分支点数组到指定长度，方便数据库查询（查询时不用去判断数数组长度了
for i in RealPoint:
    for index in range(0, 3):
        try:
            i[2][index]
        except:
            i[2].append(i[2][0])

# 友军阵容去重
for Index, i in enumerate(RealPoint):
    res = []
    Sign = []
    for j in KCClient.find({"$or": [{"$and": [{"maparea_id": MapareaId}, {"mapinfo_no": i[0]}, {"curCellId": i[2][0]}]}, {"curCellId": i[2][1]}, {"curCellId": i[2][2]}]}, {"api_ship_id": 1, "api_ship_lv": 1, "api_nowhps": 1, "api_maxhps": 1, "api_Param": 1, "api_Slot": 1, "api_voice_id": 1}):
        try:
            Sign.index(j['api_ship_id'])
        except:
            Sign.append(j['api_ship_id'])
            if(j['api_ship_id'] != []):
                res.append(j)
    i.append(res)
    print("友军阵容去重：{}/{}".format(Index+1, len(RealPoint)))

# 生成友军阵容
for Index, i in enumerate(RealPoint):
    print('生成友军阵容{}/{}'.format(Index+1, len(RealPoint)))
    wikiCodeStr = ''
    for j in i[3]:
        wikiCodeStr += "{{友军舰队\n"
        wikiCodeStr += ' | 地图点=E{}{}点\n'.format(i[0], i[1])
        wikiCodeStr += ' | 舰娘数 = {}\n'.format(len(j['api_ship_id']))
        for k in range(0, len(j['api_ship_id'])):
            wikiCodeStr += ' | 舰娘图{} = KanMusu{}HDBanner.png\n'.format(
                k+1, FoundShipDetails(j['api_ship_id'][k], 'wiki_id'))
            wikiCodeStr += ' | 等级{} = {}\n'.format(k+1, j['api_ship_lv'][k])
            wikiCodeStr += ' | 耐久{} = {}/{}\n'.format(
                k+1, j['api_nowhps'][k], j['api_maxhps'][k])
            wikiCodeStr += ' | 火力{} = {}\n'.format(k+1, j['api_Param'][k][0])
            wikiCodeStr += ' | 雷装{} = {}\n'.format(k+1, j['api_Param'][k][1])
            wikiCodeStr += ' | 对空{} = {}\n'.format(k+1, j['api_Param'][k][2])
            wikiCodeStr += ' | 装甲{} = {}\n'.format(k+1, j['api_Param'][k][3])
            wikiCodeStr += ' | 舰名{} = {}\n'.format(
                k+1, FoundShipDetails(int(j['api_ship_id'][k]), 'name'))
            for l in range(0, len(j['api_Slot'][k])):
                try:
                    j['api_Slot'][k].remove('-1')
                except:
                    break
            wikiCodeStr += ' | 装备数{} = {}\n'.format(k+1, len(j['api_Slot'][k]))
            for m in range(0, len(j['api_Slot'][k])):
                wikiCodeStr += ' | 装备图{}-{} = Soubi{}HD.png\n'.format(
                    k+1, m+1, j['api_Slot'][k][m])
                wikiCodeStr += ' | 装备名{}-{} = {}\n'.format(
                    k+1, m+1, FoundEquipmentDetails(int(j['api_Slot'][k][m]), 'name'))
        wikiCodeStr += '}}'
        wikiCodeStr += '\n'
    if not(os.path.exists('./Formations')):
        os.makedirs('./Formations')
    with open('./Formations/E{}{}点.txt'.format(i[0], i[1]), 'w', encoding='utf-8') as File:
        File.write(wikiCodeStr)

print("友军阵容已生成，位于当前目录下的Formations文件夹内")

# 友军语音去重
VoiceList = []
for i in RealPoint:
    for j in i[3]:
        for k in range(0, len(j['api_ship_id'])):
            try:
                VoiceList.index([j['api_ship_id'][k], j['api_voice_id'][k]])
            except:
                VoiceList.append([j['api_ship_id'][k], j['api_voice_id'][k]])

# 生成友军语音
if not(os.path.exists('./Voice')):
    os.makedirs('./Voice')
for Index, i in enumerate(VoiceList):
    print("正在下载友军语音：{}/{}".format(Index+1, len(VoiceList)))
    GetVoive = requests.get(
        'http://kcs.kcwiki.cn/kcs2/sound/kc{}/{}.mp3'.format(FoundShipDetails(i[0], 'filename'), i[1]))
    if(GetVoive.status_code == 200):
        with open("./Voice/{}-FriendFleet{}.mp3".format(i[0], i[1]), "wb") as Music:
            Music.write(GetVoive.content)

print("友军语音已生成，位于当前目录下的Voice文件夹内")
