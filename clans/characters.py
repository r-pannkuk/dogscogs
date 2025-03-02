import typing


CharacterID = typing.Literal["ALICE", "AYA", "CIRNO", "MEILING", "IKU", "KOMACHI", "MARISA", "PATCHOULI", "REIMU", "REISEN", "REMILIA", "SAKUYA", "SANAE", "SUIKA", "SUWAKO", "TENSHI", "OKUU", "YOUMU", "YUKARI", "YUYUKO"]

class Character(typing.TypedDict):
    name: str
    full_name: str
    icon: str
    emoji: str

Characters : typing.Dict[str, Character] = {
    "ALICE": {
        "name": "Alice",
        "full_name": "Alice Margatroid",
        "icon": "https://wiki.koumakan.jp/images/hisouten/7/7b/Alice_Icon.png",
        "emoji": "<:Alice:1345599492933554228>"
    },
    "AYA": {
        "name": "Aya",
        "full_name": "Aya Shameimaru",
        "icon": "https://wiki.koumakan.jp/images/hisouten/b/b3/Aya_Icon.png",
        "emoji": "<:Aya:1345599494120673320>"
    },
    "CIRNO": {
        "name": "Cirno",
        "full_name": "Cirno",
        "icon": "https://wiki.koumakan.jp/images/hisouten/a/a7/Cirno_Icon.png",
        "emoji": "<:Cirno:1345599495437684806>"
    },
    "MEILING": {
        "name": "Meiling",
        "full_name": "Hong Meiling",
        "icon": "https://wiki.koumakan.jp/images/hisouten/b/b8/Meiling_Icon.png",
        "emoji": "<:Meiling:1345599499971592326>"
    },
    "IKU": {
        "name": "Iku",
        "full_name": "Iku Nagae",
        "icon": "https://wiki.koumakan.jp/images/hisouten/6/68/Iku_Icon.png",
        "emoji": "<:Iku:1345599496561758330>"
    },
    "KOMACHI": {
        "name": "Komachi",
        "full_name": "Komachi Onozuka",
        "icon": "https://wiki.koumakan.jp/images/hisouten/c/c3/Komachi_Icon.png",
        "emoji": "<:Komachi:1345599497685958707>"
    },
    "MARISA": {
        "name": "Marisa",
        "full_name": "Marisa Kirisame",
        "icon": "https://wiki.koumakan.jp/images/hisouten/1/1c/Marisa_Icon.png",
        "emoji": "<:Marisa:1345599498939793419>"
    },
    "PATCHOULI": {
        "name": "Patchouli",
        "full_name": "Patchouli Knowledge",
        "icon": "https://wiki.koumakan.jp/images/hisouten/d/df/Patchouli_Icon.png",
        "emoji": "<:Patchouli:1345599501242728518>"
    },
    "REIMU": {
        "name": "Reimu",
        "full_name": "Reimu Hakurei",
        "icon": "https://wiki.koumakan.jp/images/hisouten/0/0c/Reimu_Icon.png",
        "emoji": "<:Reimu:1345599759372517406>"
    },
    "REISEN": {
        "name": "Reisen",
        "full_name": "Reisen Udongein Inaba",
        "icon": "https://wiki.koumakan.jp/images/hisouten/e/ee/Reisen_Icon.png",
        "emoji": "<:Reisen:1345599505050894366>"
    },
    "REMILIA": {
        "name": "Remilia",
        "full_name": "Remilia Scarlet",
        "icon": "https://wiki.koumakan.jp/images/hisouten/e/e6/Remilia_Icon.png",
        "emoji": "<:Remilia:1345599507609423944>"
    },
    "SAKUYA": {
        "name": "Sakuya",
        "full_name": "Sakuya Izayoi",
        "icon": "https://wiki.koumakan.jp/images/hisouten/9/94/Sakuya_Icon.png",
        "emoji": "<:Sakuya:1345599713721716768>"
    },
    "SANAE": {
        "name": "Sanae",
        "full_name": "Sanae Kochiya",
        "icon": "https://wiki.koumakan.jp/images/hisouten/b/b9/Sanae_Icon.png",
        "emoji": "<:Sanae:1345599511136833657>"
    },
    "SUIKA": {
        "name": "Suika",
        "full_name": "Suika Ibuki",
        "icon": "https://wiki.koumakan.jp/images/hisouten/7/7b/Suika_Icon.png",
        "emoji": "<:Suika:1345599703248797706>"
    },
    "SUWAKO": {
        "name": "Suwako",
        "full_name": "Suwako Moriya",
        "icon": "https://wiki.koumakan.jp/images/hisouten/1/1b/Suwako_Icon.png",
        "emoji": "<:Suika:1345599703248797706>"
    },
    "TENSHI": {
        "name": "Tenshi",
        "full_name": "Tenshi Hinanawi",
        "icon": "https://wiki.koumakan.jp/images/hisouten/4/40/Tenshi_Icon.png",
        "emoji": "<:Tenshi:1345599672307155085>"
    },
    "OKUU": {
        "name": "Okuu",
        "full_name": "Utsuho Reiuji",
        "icon": "https://wiki.koumakan.jp/images/hisouten/6/62/Utsuho_Icon.png",
        "emoji": "<:Utsuho:1345599518372266004>"
    },
    "YOUMU": {
        "name": "Youmu",
        "full_name": "Youmu Konpaku",
        "icon": "https://wiki.koumakan.jp/images/hisouten/6/60/Youmu_Icon.png",
        "emoji": "<:Youmu:1345599656226328607>"
    },
    "YUKARI": {
        "name": "Yukari",
        "full_name": "Yukari Yakumo",
        "icon": "https://wiki.koumakan.jp/images/hisouten/3/3f/Yukari_Icon.png",
        "emoji": "<:Yukari:1345599521132118099>"
    },
    "YUYUKO": {
        "name": "Yuyuko",
        "full_name": "Yuyuko Saigyouji",
        "icon": "https://wiki.koumakan.jp/images/hisouten/8/8d/Yuyuko_Icon.png",
        "emoji": "<:Yuyuko:1345599616766443572>"
    },
}