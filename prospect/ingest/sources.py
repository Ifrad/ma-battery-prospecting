"""Where each public data source lives. See docs/DATA.md for what they contain."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str
    kind: str  # "arcgis" (feature layer URL) or "ckan" (datastore resource id)
    url: str
    resource_id: str = ""


SOURCES = [
    Source(
        "parcels",
        "arcgis",
        "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/"
        "Massachusetts_Property_Tax_Parcels/FeatureServer/0",
    ),
    Source(
        "footprints",
        "arcgis",
        "https://services1.arcgis.com/hGdibHYSPO59RG1h/arcgis/rest/services/"
        "Building_Structures/FeatureServer/0",
    ),
    Source(
        "utility_territories",
        "arcgis",
        "https://arcgisserver.digital.mass.gov/arcgisserver/rest/services/"
        "AGOL/ElectricityProviders/FeatureServer/0",
    ),
    Source(
        "lber",
        "arcgis",
        "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/arcgis/rest/services/"
        "2025_Annual_Report_Data/FeatureServer/0",
    ),
    Source(
        "berdo",
        "ckan",
        "https://data.boston.gov/api/3/action/datastore_search",
        resource_id="87521565-7f15-4b8d-a225-ac4df9e3f309",
    ),
]
