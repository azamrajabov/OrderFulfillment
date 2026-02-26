import requests


class Vindecoder:
    endpoint_point_template = (
        "https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvalues/{}?format=json"
    )
    vin = ""

    def __init__(self, vin):
        self.vin = vin

    def get_vindecoded_fields(self):
        data = {"format": "json"}
        endpoint = self.endpoint_point_template.format(self.vin)
        response = requests.get(url=endpoint, data=data)
        result = response.json().get("Results")[0]
        result["EngineManufacturer"] = result.get("EngineManufacturer", "N/A") or "N/A"
        result["Model"] = result.get("Model", "N/A") or "N/A"
        # print(result)
        print(
            "Make",
            result["Make"],
            "Model",
            result["ModelYear"],
            "Engine",
            result["EngineManufacturer"],
            "Model",
            result["Model"],
        )
        if result["Make"] and result["ModelYear"] and result["EngineManufacturer"]:
            return {
                "Make": result["Make"].replace(",", ""),
                "Year": result["ModelYear"],
                "Engine": result["EngineManufacturer"].replace(",", ""),
                "Model": result["Model"].replace(",", ""),
            }

    def get_adapter(self):
        truck = self.get_vindecoded_fields()
        adapter = ""
        if not truck:
            print("No truck found", truck)
            return "", ""
        make = truck["Make"].lower()
        year = int(truck["Year"])
        engine = truck["Engine"].lower()
        if engine == "n/a" or make in ("ford", "chevrolet", "gmc", "dodge"):
            adapter = "OBD Power Cord w/type C Connector 12v"
        if "freightliner" in make:
            if year <= 2002:
                adapter = "OBD -> J1708 Adapter 6 Pin"
            elif year > 2002:
                adapter = "J1939 Power Cord 9 Pin"
        elif "kenworth" in make:
            if year <= 2005:
                adapter = "OBD -> J1708 Adapter 6 Pin"
            elif year > 2005:
                adapter = "J1939 Power Cord 9 Pin"
        elif "peterbilt" in make:
            if year <= 2005:
                adapter = "OBD -> J1708 Adapter 6 Pin"
            elif year > 2005:
                adapter = "J1939 Power Cord 9 Pin"
        elif "international" in make:
            if year <= 2005:
                adapter = "OBD -> J1708 Adapter 6 Pin"
            elif year > 2005:
                adapter = "J1939 Power Cord 9 Pin"
            if "cummins" in engine and year == 2006:
                adapter = "OBD -> J1708 Adapter 6 Pin"
        elif "volvo" in make:
            if year <= 2000:
                adapter = "OBD -> J1708 Adapter 6 Pin"
            elif engine == "volvo" and year <= 2013:
                adapter = "J1939 Power Cord 9 Pin"
            elif engine == "volvo" and year > 2013:
                adapter = "OBD Power Cord w/type C Connector 12v"
            elif "volvo d series" in engine and year >= 2006:
                adapter = "OBD Power Cord w/type C Connector 12v"
            elif "cummins" in engine and year >= 2006:
                adapter = "J1939 Power Cord 9 Pin"
        elif "mack" in make:
            if year <= 2003:
                adapter = "OBD -> J1708 Adapter 6 Pin"
            elif year > 2003 and "mack" in engine:
                adapter = "J1939 Power Cord 9 Pin"
            if year >= 2014 and "mack mp Series" in engine:
                adapter = "OBD Power Cord w/type C Connector 12v"
        elif "western star" in make:
            if year >= 2006:
                adapter = "J1939 Power Cord 9 Pin"
        elif "light/med duty" in make:
            if year >= 2008:
                adapter = "OBD Power Cord w/type C Connector 12v"

        # Gregg: Yes that is the blanket rule for anything we can't find.
        # They are likely the light utility trucks
        # Email Sat, Jun 8, 8:12 AM
        if not adapter:
            adapter = "OBD Power Cord w/type C Connector 12v"

        return truck, adapter
