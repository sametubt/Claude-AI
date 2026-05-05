"""SET100 constituents (as of late 2024 / early 2025).

Maintained as a static list to avoid scraping fragility. Each entry maps
the Thai ticker (without suffix) to a display name and a sector category
used by the frontend filter.
"""

SET100_CONSTITUENTS = [
    # Banks
    ("BBL",     "Bangkok Bank",                          "Bank"),
    ("KBANK",   "Kasikornbank",                          "Bank"),
    ("SCB",     "SCB X",                                 "Bank"),
    ("KTB",     "Krung Thai Bank",                       "Bank"),
    ("BAY",     "Bank of Ayudhya",                       "Bank"),
    ("TTB",     "TMBThanachart Bank",                    "Bank"),
    ("TISCO",   "Tisco Financial Group",                 "Bank"),
    ("KKP",     "Kiatnakin Phatra Bank",                 "Bank"),

    # Energy / Petrochem / Utilities
    ("PTT",     "PTT",                                   "Energy"),
    ("PTTEP",   "PTT Exploration and Production",        "Energy"),
    ("PTTGC",   "PTT Global Chemical",                   "Energy"),
    ("TOP",     "Thai Oil",                              "Energy"),
    ("IRPC",    "IRPC",                                  "Energy"),
    ("BCP",     "Bangchak Corporation",                  "Energy"),
    ("BANPU",   "Banpu",                                 "Energy"),
    ("EGCO",    "Electricity Generating",                "Energy"),
    ("RATCH",   "Ratch Group",                           "Energy"),
    ("GULF",    "Gulf Energy Development",               "Energy"),
    ("GPSC",    "Global Power Synergy",                  "Energy"),
    ("BGRIM",   "B.Grimm Power",                         "Energy"),
    ("EA",      "Energy Absolute",                       "Energy"),
    ("BPP",     "Banpu Power",                           "Energy"),
    ("OR",      "PTT Oil and Retail",                    "Energy"),
    ("SPRC",    "Star Petroleum Refining",               "Energy"),
    ("ESSO",    "Esso Thailand",                         "Energy"),
    ("TPIPP",   "TPI Polene Power",                      "Energy"),
    ("ACE",     "Absolute Clean Energy",                 "Energy"),

    # Property / Construction
    ("LH",      "Land and Houses",                       "Property"),
    ("AP",      "AP Thailand",                           "Property"),
    ("SPALI",   "Supalai",                               "Property"),
    ("PSH",     "Pruksa Holding",                        "Property"),
    ("QH",      "Quality Houses",                        "Property"),
    ("ORI",     "Origin Property",                       "Property"),
    ("SIRI",    "Sansiri",                               "Property"),
    ("ANAN",    "Ananda Development",                    "Property"),
    ("CPN",     "Central Pattana",                       "Property"),
    ("WHA",     "WHA Corporation",                       "Property"),
    ("AMATA",   "Amata Corporation",                     "Property"),
    ("ROJNA",   "Rojana Industrial Park",                "Property"),
    ("STEC",    "Sino-Thai Engineering",                 "Property"),
    ("CK",      "Ch. Karnchang",                         "Property"),
    ("ITD",     "Italian-Thai Development",              "Property"),
    ("SCC",     "Siam Cement Group",                     "Property"),
    ("SCCC",    "Siam City Cement",                      "Property"),
    ("TPIPL",   "TPI Polene",                            "Property"),

    # Telecom / Tech
    ("ADVANC",  "Advanced Info Service",                 "Telecom"),
    ("TRUE",    "True Corporation",                      "Telecom"),
    ("INTUCH",  "Intouch Holdings",                      "Telecom"),
    ("JMART",   "Jay Mart",                              "Telecom"),
    ("JMT",     "JMT Network Services",                  "Telecom"),
    ("SINGER",  "Singer Thailand",                       "Telecom"),
    ("SYNEX",   "Synnex (Thailand)",                     "Telecom"),
    ("COM7",    "Com7",                                  "Telecom"),

    # Food / Agri / Consumer
    ("CPF",     "Charoen Pokphand Foods",                "Food"),
    ("CPALL",   "CP All",                                "Food"),
    ("CPAXT",   "CP Axtra",                              "Food"),
    ("TU",      "Thai Union Group",                      "Food"),
    ("OSP",     "Osotspa",                               "Food"),
    ("ICHI",    "Ichitan Group",                         "Food"),
    ("CBG",     "Carabao Group",                         "Food"),
    ("M",       "MK Restaurant Group",                   "Food"),
    ("MINT",    "Minor International",                   "Food"),
    ("CRC",     "Central Retail Corporation",            "Food"),
    ("HMPRO",   "Home Product Center",                   "Food"),
    ("GLOBAL",  "Siam Global House",                     "Food"),
    ("BJC",     "Berli Jucker",                          "Food"),
    ("MAKRO",   "Siam Makro",                            "Food"),
    ("TFG",     "Thaifoods Group",                       "Food"),
    ("GFPT",    "GFPT",                                  "Food"),
    ("RBF",     "R&B Food Supply",                       "Food"),

    # Healthcare / Other
    ("BDMS",    "Bangkok Dusit Medical Services",        "Other"),
    ("BH",      "Bumrungrad Hospital",                   "Other"),
    ("BCH",     "Bangkok Chain Hospital",                "Other"),
    ("CHG",     "Chularat Hospital",                     "Other"),
    ("PR9",     "Praram 9 Hospital",                     "Other"),
    ("AOT",     "Airports of Thailand",                  "Other"),
    ("BEM",     "Bangkok Expressway and Metro",          "Other"),
    ("BTS",     "BTS Group Holdings",                    "Other"),
    ("AAV",     "Asia Aviation",                         "Other"),
    ("BA",      "Bangkok Airways",                       "Other"),
    ("DELTA",   "Delta Electronics (Thailand)",          "Other"),
    ("KCE",     "KCE Electronics",                       "Other"),
    ("HANA",    "Hana Microelectronics",                 "Other"),
    ("STA",     "Sri Trang Agro-Industry",               "Other"),
    ("STGT",    "Sri Trang Gloves",                      "Other"),
    ("TASCO",   "Tipco Asphalt",                         "Other"),
    ("DOHOME",  "Dohome",                                "Other"),
    ("BEC",     "BEC World",                             "Other"),
    ("WORK",    "Workpoint Entertainment",               "Other"),
    ("MAJOR",   "Major Cineplex Group",                  "Other"),
    ("VGI",     "VGI",                                   "Other"),
    ("PLANB",   "Plan B Media",                          "Other"),
    ("ERW",     "The Erawan Group",                      "Other"),
    ("CENTEL",  "Central Plaza Hotel",                   "Other"),
    ("KEX",     "Kerry Express (Thailand)",              "Other"),
    ("JWD",     "JWD InfoLogistics",                     "Other"),
    ("WICE",    "Wice Logistics",                        "Other"),
    ("RCL",     "Regional Container Lines",              "Other"),
    ("PSL",     "Precious Shipping",                     "Other"),
    ("TIPH",    "Tip Insurance Holding",                 "Other"),
    ("BLA",     "Bangkok Life Assurance",                "Other"),
    ("MTC",     "Muangthai Capital",                     "Other"),
    ("SAWAD",   "Srisawad Corporation",                  "Other"),
    ("KTC",     "Krungthai Card",                        "Other"),
    ("AEONTS",  "Aeon Thana Sinsap",                     "Other"),
]


def get_set100() -> list[dict]:
    """Return the SET100 list as dicts: ticker, yahoo_ticker, name, sector."""
    return [
        {
            "ticker": t,
            "yahoo_ticker": f"{t}.BK",
            "name": name,
            "sector": sector,
        }
        for t, name, sector in SET100_CONSTITUENTS
    ]
