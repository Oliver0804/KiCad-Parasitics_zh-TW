from os.path import exists
import s_expression_parse
import re


def extract_layer_from_string(input_string):
    if input_string == "F.Cu":
        return 0
    elif input_string == "B.Cu":
        return 31
    else:
        match = re.search(r"In(\d+)\.Cu", input_string)
        if match:
            return int(match.group(1))
    return None


def search_recursive(line: list, entry: str):
    if type(line[0]) == str and line[0] == entry:
        return line[1]

    for e in line:
        if type(e) == list:
            res = search_recursive(e, entry)
            if not res == None:
                return res
    return None


def Get_PCB_Stackup(ProjectPath="./test.kicad_pcb"):
    def readFile2var(path):
        if not exists(path):
            return None

        with open(path, "r") as file:
            data = file.read()
        return data

    PhysicalLayerStack = []
    CuStack = {}
    if exists(ProjectPath):
        txt = readFile2var(ProjectPath)
        parsed = s_expression_parse.parse_sexp(txt)
        for line in parsed:
            if line[0].lower() == "setup":
                abs_height = 0.0
                for layer in line[1]:
                    tmp = {}
                    tmp["layer"] = search_recursive(layer, "layer")
                    tmp["thickness"] = search_recursive(layer, "thickness")
                    tmp["epsilon_r"] = search_recursive(layer, "epsilon_r")
                    tmp["type"] = search_recursive(layer, "type")

                    if not tmp["thickness"] == None:
                        tmp["cu_layer"] = extract_layer_from_string(tmp["layer"])
                        tmp["abs_height"] = abs_height
                        abs_height += float(tmp["thickness"])
                        PhysicalLayerStack.append(tmp)
                break
        for Layer in PhysicalLayerStack:
            if not Layer["cu_layer"] == None:
                CuStack[Layer["cu_layer"]] = {
                    "thickness": Layer["thickness"],
                    "name": Layer["layer"],
                    "abs_height": Layer["abs_height"],
                }
                if Layer["thickness"] <= 0:
                    raise Exception("Problematic layer thickness detected")

    return PhysicalLayerStack, CuStack
