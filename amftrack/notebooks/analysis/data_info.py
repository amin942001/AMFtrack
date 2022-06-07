inst_25 = [
    (35, 0, 15),
    (29, 0, 20),
    (9, 0, 11),
    (9, 13, 35),
    (3, 0, 19),
    (37, 0, 8),
    (11, 0, 30),
    (19, 0, 25),
    (13, 0, 25),
    (39, 0, 18),
]
inst_bait = [
    (10, 0, 10),
    (14, 0, 11),
    (33, 0, 26),
    (4, 2, 18),
    (4, 20, 30),
    (39, 117, 137),
    (12, 5, 21),
    (28, 0, 14),
    (32, 5, 14),
    (32, 15, 44),
    (36, 0, 9),
    (40, 0, 14),
    (2, 1, 15),
    (2, 17, 35),
    (5, 160, 168),
    (11, 158, 164),
    (13, 116, 131),
]
inst_30 = []
inst_25late = [
    (32, 160, 190),
    (38, 61, 76),
    (39, 446, 466),
    (40, 153, 153 + 37),
    (39, 269, 329),
    (40, 262, 287),
    (38, 7, 42),
]
inst_25late_extended = [
    (39, 269, 369),
    (40, 153, 190),
    (38, 7, 50),
    (38, 61, 105),
    (32, 160, 199),
    (39, 446, 486),
    (35, 70, 119),
    (38, 106, 130),
    (36, 204, 233),
    (30, 57, 94),
    (29, 221, 241),
    (40, 262, 312),
    (29, 160, 184),
    (30, 0, 24),
]
inst_25_100P = [(38, 131, 131 + 80)]
# treatments = {'25*' : inst_25late,'25' : inst_25,'baits' : inst_bait, '30' : inst_30}
treatments = {
    "25_100": inst_25_100P,
    "25*": inst_25late,
    "25": inst_25,
    "baits": inst_bait,
    "30": inst_30,
}

plate_number = {
    (9, 0, 11): 296,
    (9, 13, 35): 296,
    (3, 0, 19): 340,
    (37, 0, 8): 269,
    (11, 0, 30): 314,
    (19, 0, 25): 344,
    (13, 0, 25): 298,
    (39, 0, 18): 297,
    (35, 0, 15): 351,
    (10, 0, 10): 395,
    (14, 0, 11): 399,
    (33, 0, 26): 420,
    (4, 2, 18): 423,
    (4, 20, 30): 423,
    (8, 0, 17): 434,
    (8, 20, 30): 434,
    (39, 117, 137): 433,
    (12, 5, 21): 436,
    (28, 0, 14): 405,
    (32, 5, 45): 409,
    (36, 0, 9): 419,
    (40, 0, 14): 425,
    (2, 1, 15): 435,
    (2, 17, 35): 435,
    (5, 160, 168): 382,
    (11, 158, 164): 416,
    (13, 116, 131): 424,
    (29, 0, 20): 373,
    (32, 15, 44): 409,
    (32, 5, 14): 409,
    (40, 153, 153 + 37): 69,
    (39, 269, 329): 94,
    (40, 262, 287): 102,
    (38, 7, 42): 59,
    (32, 160, 190): 152,
    (38, 61, 76): 137,
    (39, 446, 466): 26,
    (38, 131, 131 + 80): 721,
}

comments = {
    395: "ignore",
    399: "left",
    405: "left",
    409: "right",
    416: "middle",
    419: "middle",
    420: "left",
    423: "right",
    424: "left",
    425: "middle",
    433: "right",
    435: "middle",
    436: "left",
}
