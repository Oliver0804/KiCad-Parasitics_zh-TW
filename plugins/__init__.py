import pcbnew
from importlib import reload
import sys
import os
import wx
import traceback
from pprint import pprint
from pathlib import Path
import math


# import pip
# def install(package):
#     if hasattr(pip, "main"):
#         pip.main(["install", package])
#     else:
#         pip._internal.main(["install", package])
# install("PySpice")
# import PySpice

debug = 0


class ActionKiCadPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "寄生參數計算"
        self.category = "寄生參數"
        self.description = "計算兩點間的寄生參數"
        self.show_toolbar_button = True
        self.plugin_path = os.path.dirname(__file__)
        self.icon_file_name = os.path.join(self.plugin_path, "icon_small.png")
        self.dark_icon_file_name = os.path.join(self.plugin_path, "icon_small.png")

        # 將目前目錄加入模組路徑
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(current_dir)

    def Run(self):
        try:
            print("###############################################################")

            import Get_PCB_Elements
            import Connect_Nets
            import Get_PCB_Stackup
            import Get_Parasitic

            board = pcbnew.GetBoard()
            connect = board.GetConnectivity()
            Settings = pcbnew.GetSettingsManager()

            # KiCad_CommonSettings = Settings.GetCommonSettings()
            KiCad_UserSettingsPath = Settings.GetUserSettingsPath()
            KiCad_SettingsVersion = Settings.GetSettingsVersion()
            board_FileName = Path(board.GetFileName())

            ####################################################
            # 獲取 PCB 元件
            ####################################################

            if debug:
                reload(Get_PCB_Elements)
            from Get_PCB_Elements import Get_PCB_Elements, SaveDictToFile

            ItemList = Get_PCB_Elements(board, connect)

            ####################################################
            # 儲存變數 ItemList 以供除錯
            ####################################################

            if debug:
                save_as_file = os.path.join(self.plugin_path, "ItemList.py")
                print("儲存檔案", save_as_file)
                SaveDictToFile(ItemList, save_as_file)
                with open(save_as_file, "a") as f:
                    f.write('\nboard_FileName = "')
                    f.write(str(board_FileName))
                    f.write('"')

            ####################################################
            # 連接網路
            ####################################################

            if debug:
                reload(Connect_Nets)
            from Connect_Nets import Connect_Nets

            data = Connect_Nets(ItemList)
            # pprint(data)

            ####################################################
            # 讀取物理層堆疊
            ####################################################

            if debug:
                reload(Get_PCB_Stackup)
            from Get_PCB_Stackup import Get_PCB_Stackup

            PhysicalLayerStack, CuStack = Get_PCB_Stackup(ProjectPath=board_FileName)
            # pprint(CuStack)

            ####################################################
            # 計算電阻
            ####################################################

            if debug:
                reload(Get_Parasitic)
            from Get_Parasitic import Get_Parasitic

            Selected = [d for uuid, d in list(data.items()) if d["IsSelected"]]

            message = ""
            if len(Selected) == 2:
                conn1 = Selected[0]["netStart"][Selected[0]["Layer"][0]]
                conn2 = Selected[1]["netStart"][Selected[1]["Layer"][0]]
                NetCode = Selected[0]["NetCode"]
                if not NetCode == Selected[1]["NetCode"]:
                    message = "標記的兩個點不在相同的網路中。"
            else:
                message = "您必須標記正好兩個元件。\n建議標記焊盤或過孔。"

            if message == "":
                (
                    Resistance,
                    Distance,
                    inductance_nH,
                    short_path_RES,
                    Area,
                ) = Get_Parasitic(data, CuStack, conn1, conn2, NetCode)

                message += "\n兩個標記點之間的最短距離 ≈ "
                message += "{:.3f} mm".format(Distance)

                message += "\n"
                if not PhysicalLayerStack:
                    message += "\n未找到物理堆疊！"
                if short_path_RES > 0:
                    message += "\n短路路徑的電阻 ≈ "
                    message += "{:.3f} mΩ".format(short_path_RES * 1000)
                elif short_path_RES == 0:
                    message += "\n短路路徑的電阻 ≈ {:.3f} mΩ".format(short_path_RES * 1000)
                    message += "\n假設區域完全導電並短路。"
                else:
                    message += "\n未找到標記點之間的任何連接。"

                if not math.isinf(Resistance) and Resistance >= 0:
                    message += "\n兩點之間的電阻 ≈ "
                    message += "{:.3f} mΩ".format(Resistance * 1000)
                elif Resistance < 0:
                    message += "\n電阻網路計算發生錯誤，可能是未找到 ngspice 安裝。"
                    message += "\n短路路徑的結果未受影響。"
                else:
                    message += "\n未找到標記點之間的任何連接。"

                message += "\n"
                if inductance_nH > 0:
                    message += "\n計算出的自感 ≈ "
                    message += "{:.3f} nH".format(inductance_nH)
                    message += "\n假設導線在無地平面環境下。"
                    message += "\n結果需特別注意！"
                else:
                    message += "\n計算出的自感 ≈ 無效"
                    message += "\n對於直接連接無間斷的情況，計算不適用。"

                message += "\n"
                if len(Area) > 0:
                    message += "\n信號的粗略面積估算（不含區域和過孔）："
                    for layer in Area.keys():
                        message += "\n圖層 {}: {:.3f} mm², {} μm 銅層".format(
                            CuStack[layer]["name"],
                            Area[layer],
                            CuStack[layer]["thickness"] * 1000,
                        )

            dlg = wx.MessageDialog(
                None,
                message,
                "分析結果",
                wx.OK,
            )
            dlg.ShowModal()
            dlg.Destroy()

            ####################################################
            # 繪製 PCB
            ####################################################

            # if debug:
            #     from Plot_PCB import Plot_PCB
            #     Plot_PCB(data)

        except Exception as e:
            dlg = wx.MessageDialog(
                None,
                traceback.format_exc(),
                "致命錯誤",
                wx.OK | wx.ICON_ERROR,
            )
            dlg.ShowModal()
            dlg.Destroy()

        pcbnew.Refresh()


if not __name__ == "__main__":
    ActionKiCadPlugin().register()

if __name__ == "__main__":
    from ItemList import data, board_FileName  # 或者使用：import Get_PCB_Elements
    from Connect_Nets import Connect_Nets
    from Get_PCB_Stackup import Get_PCB_Stackup
    from Get_Parasitic import Get_Parasitic
    from Plot_PCB import Plot_PCB

    # 獲取 PCB 元件
    ItemList = data

    # 連接網路
    data = Connect_Nets(ItemList)
    # pprint(data)

    # 從檔案中讀取物理層堆疊
    PhysicalLayerStack, CuStack = Get_PCB_Stackup(ProjectPath=board_FileName)
    pprint(CuStack)

    # 計算電阻
    Selected = [d for uuid, d in list(data.items()) if d["IsSelected"]]
    if len(Selected) == 2:
        conn1 = Selected[0]["netStart"][Selected[0]["Layer"][0]]
        conn2 = Selected[1]["netStart"][Selected[1]["Layer"][0]]
        NetCode = Selected[0]["NetCode"]
        if not NetCode == Selected[1]["NetCode"]:
            print("標記的兩個點不在相同的網路中。")

        Resistance, Distance, inductance_nH, short_path_RES, Area = Get_Parasitic(
            data, CuStack, conn1, conn2, NetCode
        )
        print("距離 (mm)：", Distance)
        print("電阻 (mΩ)：", Resistance)
        print("短路路徑的電阻 (mΩ)：", short_path_RES)
        print("自感 (nH)：", inductance_nH)
        print("面積 (mm²)：", Area)

        if len(Area) > 0:
            for layer in Area.keys():
                txt = "圖層 {}: {:.3f} mm²".format(layer, Area[layer])
                print(txt)
    else:
        print("您必須標記正好兩個元件。")

    # 使用 matplotlib 繪製 PCB
    # Plot_PCB(data)
