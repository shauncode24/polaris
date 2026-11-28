"""Which spellings are one and the same name.

Stricter than `CANONICAL_SKILLS`, which groups what counts as evidence of a
skill: "version control" is evidence of Git, but it isn't another way to write
it. Only exact equivalents belong here, since one of them may stand in for
another on a resume: not a product for an activity, not a narrower or broader
term, not a plural for a singular, and not a spelling that is also an ordinary
word ("node", "rest").
"""

# Each group is one name; the first spelling stands for the rest.
SAME_NAME = (
    ("postgresql", "postgres"),
    ("mongodb", "mongo"),
    ("kubernetes", "k8s"),
    ("javascript", "js"),
    ("react.js", "react", "reactjs", "react js"),
    ("vue.js", "vuejs", "vue js", "vue"),
    ("node.js", "nodejs", "node js"),
    ("next.js", "nextjs"),
    ("express.js", "expressjs"),
    ("three.js", "threejs"),
    ("spring boot", "spring-boot", "springboot"),
    ("fastapi", "fast api"),
    ("scikit-learn", "scikit learn", "sklearn"),
    ("c++", "cpp"),
    ("c#", "c sharp"),
    ("amazon web services", "aws"),
    ("google cloud platform", "gcp"),
    ("amazon s3", "aws s3"),
    ("ci/cd", "ci-cd", "cicd", "ci cd"),
    ("elasticsearch", "elastic search"),
    ("machine learning", "ml"),
    ("object-oriented programming", "object oriented programming", "oop"),
    ("microservices", "micro services", "micro-services"),
    ("microservice", "micro service", "micro-service"),
    ("restful apis", "rest apis"),
    ("restful api", "rest api"),
    ("%", "percent", "per cent"),
)
NAME_OF = {spelling: names[0] for names in SAME_NAME for spelling in names}


def same_name(first: str, second: str) -> bool:
    """True when the two are the same name, whatever the capitals or spacing."""
    def name(text: str) -> str:
        plain = " ".join(text.lower().split())
        return NAME_OF.get(plain, plain)

    return name(first) == name(second)
