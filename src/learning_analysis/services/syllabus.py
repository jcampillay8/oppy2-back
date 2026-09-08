# src/learning_analysis/services/syllabus.py

# A representation of English_Path.md
ENGLISH_PATH_SYLLABUS = {
    1: {
        "cefr": "A1",
        "units": {
            1: "It's nice to meet you",
            2: "All about you",
            3: "What's your schedule?",
            4: "What's he like?",
            5: "A day in the life",
            6: "What is that?",
            7: "How do you get there?",
            8: "How much?"
        }
    },
    2: {
        "cefr": "A2",
        "units": {
            1: "What can you do?",
            2: "What's going on?",
            3: "It was great!",
            4: "Yesterday",
            5: "Home sweet home",
            6: "How much do you want?",
            7: "Going out",
            8: "That's my mom!"
        }
    },
    3: {
        "cefr": "A2+",
        "units": {
            1: "Making comparasions",
            2: "Have you ever been to Paris?",
            3: "Life stories",
            4: "Where are you going?",
            5: "What's your problem?",
            6: "Negotiating",
            7: "What if?",
            8: "I'm right aren't?"
        }
    },
    4: {
        "cefr": "A2+/B1",
        "units": {
            1: "What's new?",
            2: "What are they like?",
            3: "What were you doing?",
            4: "Amazing experiences",
            5: "What I've done",
            6: "Plans for the future",
            7: "Why did they do it?",
            8: "What did you decide?"
        }
    },
    5: {
        "cefr": "B1",
        "units": {
            1: "Talking about the past",
            2: "A chance for the better",
            3: "Around the world",
            4: "Good news travels fast!",
            5: "If only I had known!",
            6: "When things go wrong",
            7: "What happened?",
            8: "Blast to the future"
        }
    },
    6: {
        "cefr": "B1+/B2",
        "units": {
            1: "Telling a story",
            2: "Describing people",
            3: "Discoveries and inventions",
            4: "Products and ideas",
            5: "Working together",
            6: "Corporate culture",
            7: "Gathering Information",
            8: "Taking about numbers"
        }
    }
}

def get_level_cefr(level: int) -> str:
    level_data = ENGLISH_PATH_SYLLABUS.get(level)
    return level_data["cefr"] if level_data else "B1"

def get_topic_for_unit(level: int, unit: int) -> str:
    level_data = ENGLISH_PATH_SYLLABUS.get(level)
    if level_data:
        return level_data["units"].get(unit, "General Conversation")
    return "General Conversation"
