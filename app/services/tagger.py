import logging
import re
from typing import List

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from app.config import MAX_AUTO_TAGS, MIN_TAG_LENGTH, MAX_TAG_LENGTH

logger = logging.getLogger(__name__)

STOP_WORDS = set([
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more",
    "most", "my", "myself", "nor", "of", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "with", "would", "you",
    "your", "yours", "yourself", "yourselves"
])

def _extract_rake_keywords(text: str) -> List[str]:
    """
    A simplified RAKE (Rapid Automatic Keyword Extraction) algorithm.
    Splits text by punctuation and stop words to find candidate phrases,
    then scores them by word frequency and degree.
    """
    words = re.split(r'\W+', text.lower())
    phrases = []
    current_phrase = []
    
    for word in words:
        if not word or word in STOP_WORDS or word.isdigit():
            if current_phrase:
                phrases.append(" ".join(current_phrase))
                current_phrase = []
        else:
            current_phrase.append(word)
    if current_phrase:
        phrases.append(" ".join(current_phrase))
        
    word_freq = {}
    word_degree = {}
    for phrase in phrases:
        phrase_words = phrase.split()
        length = len(phrase_words)
        for word in phrase_words:
            word_freq[word] = word_freq.get(word, 0) + 1
            word_degree[word] = word_degree.get(word, 0) + length
            
    phrase_scores = {}
    for phrase in phrases:
        score = 0
        for word in phrase.split():
            if word_freq[word] > 0:
                score += word_degree[word] / word_freq[word]
        phrase_scores[phrase] = score
        
    sorted_phrases = sorted(phrase_scores.keys(), key=lambda k: phrase_scores[k], reverse=True)
    return sorted_phrases[:MAX_AUTO_TAGS]

def generate_tags(text: str) -> List[str]:
    """
    Generates a list of relevant tags from the input text using a combination
    of TF-IDF and a simplified RAKE algorithm. Deduplicates and limits the output.
    """
    if not text.strip():
        return []
        
    tags = set()
    
    if HAS_SKLEARN:
        try:
            vectorizer = TfidfVectorizer(stop_words='english', max_features=MAX_AUTO_TAGS)
            vectorizer.fit([text])
            feature_names = vectorizer.get_feature_names_out()
            for name in feature_names:
                tags.add(name)
        except Exception as e:
            logger.warning(f"TF-IDF tagging failed: {e}")
            
    rake_tags = _extract_rake_keywords(text)
    for tag in rake_tags:
        tags.add(tag)
        
    valid_tags = []
    for tag in tags:
        tag_cleaned = tag.strip().lower()
        if MIN_TAG_LENGTH <= len(tag_cleaned) <= MAX_TAG_LENGTH:
            valid_tags.append(tag_cleaned)
            
    return list(set(valid_tags))[:MAX_AUTO_TAGS]
