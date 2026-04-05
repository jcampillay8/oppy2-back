LABELS = [
    "direct family relationship",
    "proper noun of a person, animal, place, or named entity",
    "characteristic or quality (adjective)",
    "action or event that is happening, happened, or will happen",
    "geographical or spatial location",
    "generic personal reference",
    "speaker's intention or goal",
    "subjective judgment or feeling",
    "problem or difficulty that requires a solution",
    "tangible object or material item",
    "name of an organization or team",
    "specific temporal reference"
]

LABEL_TO_FACT_TYPE = {
    "direct family relationship": "relationship",
    "proper noun of a person, animal, place, or named entity": "named_entity",
    "characteristic or quality (adjective)": "characteristic",
    "action or event that is happening, happened, or will happen": "event",
    "geographical or spatial location": "location",
    "generic personal reference": "person_reference",
    "speaker's intention or goal": "intention",
    "subjective judgment or feeling": "feeling",
    "problem or difficulty that requires a solution": "problem",
    "tangible object or material item": "object",
    "name of an organization or team": "organization",
    "specific temporal reference": "time_reference",
}

# Mapeo simple (podrías tener un mapeo más robusto si manejas muchos idiomas)
LANGUAGE_MAP = {
    "es": "Spanish",
    "en-us": "English (American)",
    "en-uk": "English (British)",
    "en-gb": "English (British)",
    # Añade más según necesites, o usa una librería como `langcodes`
}