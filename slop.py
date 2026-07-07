import json

with open("dhc_variables.json", encoding="utf-8") as f:
    data = json.load(f)

variables = data["variables"]

for var, info in variables.items():

    label = str(info.get("label", ""))

    if "Asian alone" in label:
        print(var, "|", label)