"""Pinned, dated sources from the official Bank Al-Maghrib website.

A checksum identifies the exact PDF edition. It does not certify that the
edition reflects legislation currently in force.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    language: str
    url: str
    sha256: str
    filename: str
    version_date: str = "2022-03-31"
    document_id: str = "law-103-12"
    expected_pages: int = 84

    def metadata(self) -> dict:
        return asdict(self)


# Article 19 bis follows article 19, before article 20.
EXPECTED_ARTICLE_IDS = (
    tuple(str(number) for number in range(1, 20))
    + ("19bis",)
    + tuple(str(number) for number in range(20, 197))
)

SOURCES = (
    SourceSpec(
        source_id="bam-10312-fr",
        language="fr",
        url="https://www.bkam.ma/fr/content/download/757666/8545663/loi%20bancaire%20fr.pdf",
        sha256="663038cf056a377d9f7ab1d31ad1136077440c8bcada92ee9c116ef41791a56a",
        filename="bam-10312-fr.pdf",
    ),
    SourceSpec(
        source_id="bam-10312-ar",
        language="ar",
        url=(
            "https://www.bkam.ma/ar/content/download/757666/8545665/"
            "loi%20bancaire%20ar%2022%20V2%20web.pdf"
        ),
        sha256="ac1453c87ee9ecd17a29c0e47320686d75ecd4d5b4d34099b903ccddcc2cd790",
        filename="bam-10312-ar.pdf",
    ),
)
SOURCE_CATALOG = {source.source_id: source for source in SOURCES}
