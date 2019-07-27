# -*- coding: utf-8 -*-

'''
@author: hzw77, gjz5038

python runexp.py

Run experiments in batch with configuration

'''

# ================================= only change these two ========================================
SEED = 31200

setting_memo = "one_run"
#setting_memo = "inga"

# ================================= only change these two ========================================


import random
random.seed(SEED)
import numpy as np
np.random.seed(SEED)
from tensorflow import set_random_seed
set_random_seed((SEED))
import json
import os
import traffic_light_dqn
import time

PATH_TO_CONF = os.path.join("conf", setting_memo)


# Binaries and commands with GUI
sumoBinary = "C:\Program Files (x86)\Eclipse\Sumo\\bin\sumo-gui.exe"
sumoCmd = [sumoBinary,
           '-c',
           "D:\Google Drive\Estudos\Faculdade\\2019.2\Projeto Final II\Repositórios\IntelliLight\data\one_run\cross.sumocfg"]
sumoCmd_pretrain = [sumoBinary,
                    '-c',
                    "D:\Google Drive\Estudos\Faculdade\\2019.2\Projeto Final II\Repositórios\IntelliLight\data\one_run\cross_pretrain.sumocfg"]

# Binaries and commands without GUI
sumoBinary_nogui = "C:\Program Files (x86)\Eclipse\Sumo\\bin\sumo.exe"
sumoCmd_nogui = [sumoBinary_nogui,
                 '-c',
                 'D:\Google Drive\Estudos\Faculdade\\2019.2\Projeto Final II\Repositórios\IntelliLight\data\one_run\cross.sumocfg']
sumoCmd_nogui_pretrain = [sumoBinary_nogui,
                          '-c',
                          "D:\Google Drive\Estudos\Faculdade\\2019.2\Projeto Final II\Repositórios\IntelliLight\data\one_run\cross_pretrain.sumocfg"]


# first column: for train, second column: for spre_train
list_traffic_files = [
    [["cross.2phases_rou1_switch_rou0.xml"], ["cross.2phases_rou1_switch_rou0.xml"]],
    [["cross.2phases_rou01_equal_300s.xml"], ["cross.2phases_rou01_equal_300s.xml"]],
    [["cross.2phases_rou01_unequal_5_300s.xml"], ["cross.2phases_rou01_unequal_5_300s.xml"]],
    [["cross.all_synthetic.rou.xml"], ["cross.all_synthetic.rou.xml"]],
]
list_model_name = ["Deeplight"]


for model_name in list_model_name:
    # They are both the same file
    for traffic_file, traffic_file_pretrain in list_traffic_files:
        dic_exp = json.load(open(os.path.join(PATH_TO_CONF, "exp.conf"), "r"))
        dic_exp["MODEL_NAME"] = model_name
        dic_exp["TRAFFIC_FILE"] = traffic_file
        dic_exp["TRAFFIC_FILE_PRETRAIN"] = traffic_file_pretrain
        if "real" in traffic_file[0]:
            dic_exp["RUN_COUNTS"] = 86400
        elif "2phase" in traffic_file[0]:
            dic_exp["RUN_COUNTS"] = 72000
        elif "synthetic" in traffic_file[0]:
            dic_exp["RUN_COUNTS"] = 216000
        json.dump(dic_exp, open(os.path.join(PATH_TO_CONF, "exp.conf"), "w"), indent=4)

        # change MIN_ACTION_TIME correspondingly
        # TODO: what does MIN_ACTION_TIME do?
        dic_sumo = json.load(open(os.path.join(PATH_TO_CONF, "sumo_agent.conf"), "r"))
        if model_name == "Deeplight":
            dic_sumo["MIN_ACTION_TIME"] = 5
        else:
            dic_sumo["MIN_ACTION_TIME"] = 1
        json.dump(dic_sumo, open(os.path.join(PATH_TO_CONF, "sumo_agent.conf"), "w"), indent=4)

        prefix = "{0}_{1}_{2}_{3}".format(
            dic_exp["MODEL_NAME"],
            dic_exp["TRAFFIC_FILE"],
            dic_exp["TRAFFIC_FILE_PRETRAIN"],
            time.strftime('%m_%d_%H_%M_%S_', time.localtime(time.time())) + "seed_%d" % SEED
        )

        # Here you can choose to either run with a GUI or not
        traffic_light_dqn.main(memo=setting_memo, f_prefix=prefix, sumo_cmd_str=sumoCmd_nogui, sumo_cmd_pretrain_str=sumoCmd_nogui_pretrain)

        print("finished {0}".format(traffic_file))
    print("finished {0}".format(model_name))



