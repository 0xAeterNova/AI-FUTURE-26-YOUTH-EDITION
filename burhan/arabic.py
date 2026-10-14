"""Arabic search normalization WITHOUT altering the original cited documents."""
import re
import unicodedata

DIACRITICS = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")
WORDS = re.compile(r"[\u0621-\u064a]+|[a-z]+|[0-9]+", re.UNICODE)
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
STOP = {"في", "من", "الى", "علي", "عن", "هل", "ما", "ماذا", "متي", "اين", "كيف", "كم", "مع", "او", "و", "ف", "ثم", "التي", "الذي", "هذه", "هذا", "هو", "هي", "انا", "انت", "يمكن", "هناك", "لدي", "عندي", "بدي", "اريد", "شو", "ايش", "اي", "لمن", "لل", "له", "لها", "متى", "اذا", "على", "اذا", "بعد", "قبل", "هل", "من", "خلال"}
# Fixed deterministic dialect and paraphrase expansion; not dependent on another model.
SYNONYMS = [
    {"رسوم", "رسم", "التكلفه", "تكلفه", "تكاليف", "ثمن", "سعر", "مبلغ", "دفع", "مصاري", "قديش", "بكم", "بتكلف", "بتكلفني", "تكلفني"},
    {"وثائق", "اوراق", "مستندات", "مرفقات", "المطلوبه", "اللازمه", "اثباتات", "بجيب", "اجيب", "الاوراق"},
    {"شروط", "متطلبات", "اهليه", "شرط", "مؤهلات"},
    {"مده", "وقت", "ايام", "يوم", "الزمن", "استغراق", "يستغرق", "ساعات"},
    {"خطوات", "اجراءات", "كيفيه", "طريقه", "تقديم", "تقدم", "الطلب"},
    {"مكان", "عنوان", "موقع", "وين", "اين", "مكتب", "دائره"},
    {"الكتروني", "اونلاين", "انترنت", "رقمي", "موقع", "منصه"},
    {"استثناء", "استثناءات", "اعفاء", "معفي", "حالات", "استثنائي"},
    {"تجديد", "تمديد", "اعاده"},
    {"الغاء", "ابطال", "ايقاف"},
]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(ARABIC_DIGITS).lower()
    t = DIACRITICS.sub("", t).replace("ـ", "")
    t = t.translate(str.maketrans({"أ":"ا", "إ":"ا", "آ":"ا", "ٱ":"ا", "ى":"ي", "ؤ":"و", "ئ":"ي", "ة":"ه"}))
    return re.sub(r"\s+", " ", t).strip()


def tokens(text: str, expand: bool = False) -> list[str]:
    original = [w for w in WORDS.findall(normalize(text)) if len(w) > 1 and w not in STOP]
    result = list(original)
    for w in original:
        # Preserve original; only augment common clitic variants for Arabic words.
        base = w
        if len(w) > 5 and w[0] in "وفبل":
            base = w[1:]
            result.append(base)
        if len(base) > 5 and base.startswith("ال"):
            result.append(base[2:])
    if expand:
        seen = set(result)
        for group in SYNONYMS:
            normalized_group = {normalize(v) for v in group}
            if normalized_group & seen:
                result.extend(sorted(normalized_group - seen))
                seen |= normalized_group
    return result


def character_ngrams(text: str, n: int = 3) -> dict[str, int]:
    from collections import Counter
    return dict(Counter(ng for w in WORDS.findall(normalize(text)) for ng in
                        (w[i:i+n] for i in range(max(0, len(w)-n+1))) if len(ng) == n))


def digits_in(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", normalize(text)))
