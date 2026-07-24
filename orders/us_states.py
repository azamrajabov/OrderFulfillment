"""Normalize state / province names to the 2-letter codes UPS expects.

Some clients post the full name ("Minnesota") instead of the code ("MN") in
`address.state`. UPS rejects those with error 120206 "Missing or invalid ship
to state province code", so the order fails before it ever reaches the label.
"""

import re

STATE_NAMES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "districtofcolumbia": "DC",
    "washingtondc": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "newhampshire": "NH",
    "newjersey": "NJ",
    "newmexico": "NM",
    "newyork": "NY",
    "northcarolina": "NC",
    "northdakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhodeisland": "RI",
    "southcarolina": "SC",
    "southdakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "westvirginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
    # US territories / military
    "americansamoa": "AS",
    "guam": "GU",
    "northernmarianaislands": "MP",
    "puertorico": "PR",
    "virginislands": "VI",
    "usvirginislands": "VI",
    "armedforcesamericas": "AA",
    "armedforceseurope": "AE",
    "armedforcespacific": "AP",
    # Canadian provinces / territories
    "alberta": "AB",
    "britishcolumbia": "BC",
    "manitoba": "MB",
    "newbrunswick": "NB",
    "newfoundlandandlabrador": "NL",
    "newfoundland": "NL",
    "northwestterritories": "NT",
    "novascotia": "NS",
    "nunavut": "NU",
    "ontario": "ON",
    "princeedwardisland": "PE",
    "quebec": "QC",
    "saskatchewan": "SK",
    "yukon": "YT",
}

STATE_CODES = set(STATE_NAMES.values())


def normalize_state_code(state):
    """Return the 2-letter code for `state`.

    Codes are passed through (upper-cased), full names are looked up ignoring
    case, spaces and punctuation ("new york", "N.Y.", "New  York" -> "NY").
    Anything unrecognized is returned stripped and unchanged so UPS still gets
    to report it.
    """
    if not isinstance(state, str):
        return state
    cleaned = state.strip()
    if not cleaned:
        return cleaned
    key = re.sub(r"[^a-z]", "", cleaned.lower())
    if len(key) == 2 and key.upper() in STATE_CODES:
        return key.upper()
    return STATE_NAMES.get(key, cleaned)


def normalize_address_state(address):
    """Normalize `address["state"]` in place; returns the same address."""
    if isinstance(address, dict) and address.get("state") is not None:
        state = normalize_state_code(address["state"])
        if state != address["state"]:
            print(
                "Normalized address state",
                repr(address["state"]),
                "->",
                repr(state),
            )
        address["state"] = state
    return address
