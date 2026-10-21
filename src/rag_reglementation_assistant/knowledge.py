"""Internally reviewed propositions; authored summaries, never PDF fixtures.

This bounded catalogue is an explicit retrieval expansion and response template.
It is not a general-purpose entailment judge or independent legal validation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    id: str
    topic: str
    facets: tuple[str, ...]
    refs: tuple[str, ...]
    fr: str
    ar: str


def c(n):
    return f"bam-complaints-2023-fr:article-{n}"


def m(n):
    return f"bam-mediation-2023-fr:article-{n}"


FACTS = [
    Fact(
        "complaint-definition",
        "complaints",
        ("definition",),
        (c(1),),
        "La réclamation est une déclaration de différend, d’insatisfaction ou de contestation adressée à l’établissement au sujet d’un produit ou service souscrit ou envisagé.",
        "الشكاية تصريح بخلاف أو عدم رضا أو اعتراض موجه إلى المؤسسة بشأن منتج أو خدمة مكتتب فيها أو يراد الاكتتاب فيها.",
    ),
    Fact(
        "complaint-information",
        "complaints",
        ("information",),
        (c(2),),
        "L’établissement informe sa clientèle sur les interlocuteurs, canaux, modalités et délais internes, et sur les dispositifs externes de Bank Al-Maghrib et de médiation auxquels il adhère.",
        "تُطلع المؤسسة زبناءها على جهات وقنوات وكيفيات وآجال المعالجة الداخلية، وعلى آليات بنك المغرب والوساطة التي تنخرط فيها.",
    ),
    Fact(
        "complaint-ack",
        "complaints",
        ("acknowledgement",),
        (c(3),),
        "L’établissement accuse immédiatement réception de la réclamation. Cette étape est distincte de la décision de non-recevabilité.",
        "تؤكد المؤسسة فوراً توصلها بالشكاية. وتختلف هذه المرحلة عن البت في عدم القبول.",
    ),
    Fact(
        "complaint-admissibility",
        "complaints",
        ("admissibility",),
        (c(3),),
        "La décision de non-recevabilité est encadrée par dix jours ouvrés. Le refus doit être motivé et indiquer les voies de recours. La formulation du point de départ dans le recueil appelle une vérification sur la page citée.",
        "يؤطر أجل عشرة أيام عمل البت في عدم القبول. ويجب تعليل الرفض وبيان سبل الطعن. وتستدعي صياغة بداية الأجل في المجموع التحقق من الصفحة المشار إليها.",
    ),
    Fact(
        "complaint-response",
        "complaints",
        ("response_deadline", "extension"),
        (c(4),),
        "Le délai de réponse est de quarante jours ouvrés à compter de la réception de la réclamation. Si des circonstances particulières empêchent son respect, l’établissement informe le client et communique le nouveau délai d’instruction.",
        "أجل الرد هو أربعون يوم عمل ابتداء من التوصل بالشكاية. وإذا حالت ظروف خاصة دون احترامه، تُخبر المؤسسة الزبون وتبلغه بالأجل الجديد لدراسة الشكاية.",
    ),
    Fact(
        "complaint-unit",
        "complaints",
        ("organization",),
        (c(5),),
        "Une entité centrale traite et suit les réclamations avec un effectif suffisant et qualifié et des moyens techniques adaptés.",
        "تتولى وحدة مركزية معالجة الشكايات وتتبعها بموارد بشرية كافية ومؤهلة ووسائل تقنية ملائمة.",
    ),
    Fact(
        "complaint-channel",
        "complaints",
        ("procedure",),
        (c(6),),
        "Le client peut saisir son interlocuteur habituel, notamment le chargé de clientèle ou le directeur d’agence, puis l’entité centrale si la réponse ne le satisfait pas.",
        "يمكن للزبون اللجوء إلى مخاطبه المعتاد، ولا سيما المكلف بالزبناء أو مدير الوكالة، ثم إلى الوحدة المركزية إذا لم يرضه الرد.",
    ),
    Fact(
        "complaint-system",
        "complaints",
        ("information_system",),
        (c(8),),
        "Le système d’information centralise les réclamations, génère les accusés de réception, alerte sur les dépassements et produit des indicateurs et tableaux de bord.",
        "يجمع نظام المعلومات الشكايات ويصدر إشعارات التوصل وينبه إلى تجاوز الآجال وينتج مؤشرات ولوحات قيادة.",
    ),
    Fact(
        "complaint-control",
        "complaints",
        ("controls",),
        (c(9),),
        "Des contrôles permanents et périodiques couvrent les agences, l’entité centrale et les métiers concernés, notamment les dysfonctionnements récurrents.",
        "تشمل المراقبة المستمرة والدورية الوكالات والوحدة المركزية والأنشطة المعنية، ولا سيما الاختلالات المتكررة.",
    ),
    Fact(
        "complaint-client-unit",
        "complaints",
        ("client_unit",),
        (c(10),),
        "L’unité relation Clients examine les dysfonctionnements et les actions correctives. Selon le recueil, elle se réunit au moins une fois par semestre.",
        "تفحص وحدة العلاقة مع الزبناء الاختلالات والإجراءات التصحيحية. وتجتمع مرة واحدة على الأقل في كل نصف سنة وفق المجموع.",
    ),
    Fact(
        "complaint-audit",
        "complaints",
        ("audit",),
        (c(11),),
        "Le comité d’audit évalue le dispositif au moins annuellement sur la base de reportings spécifiques.",
        "تقيّم لجنة التدقيق الآلية مرة واحدة على الأقل سنوياً بالاستناد إلى تقارير مخصصة.",
    ),
    Fact(
        "complaint-training",
        "complaints",
        ("training",),
        (c(12),),
        "Les personnels concernés bénéficient d’une formation à l’identification, à la qualification et aux circuits des réclamations, et disposent des éléments du dispositif.",
        "يستفيد العاملون المعنيون من تكوين لتحديد الشكايات وتصنيفها واستعمال مسالك معالجتها، وتتاح لهم عناصر الآلية.",
    ),
    Fact(
        "complaint-reporting",
        "complaints",
        ("reporting",),
        (c(13),),
        "Les établissements transmettent à Bank Al-Maghrib un reporting trimestriel des réclamations, selon le format et les conditions qu’elle fixe. Le format détaillé n’est pas fourni par cet article.",
        "ترسل المؤسسات إلى بنك المغرب تقريراً كل ثلاثة أشهر عن الشكايات وفق الشكل والشروط التي يحددها. ولا تورد هذه المادة الشكل التفصيلي.",
    ),
    Fact(
        "complaint-internal-report",
        "complaints",
        ("internal_report",),
        (c(14),),
        "Le rapport sur le contrôle interne comprend un chapitre consacré au dispositif de réclamations et aux contrôles effectués.",
        "يتضمن تقرير المراقبة الداخلية فصلاً عن آلية الشكايات وأعمال المراقبة المنجزة.",
    ),
    Fact(
        "mediation-purpose",
        "mediation",
        ("definition",),
        (m(1),),
        "La médiation vise le règlement amiable des différends entre les établissements de crédit et leur clientèle.",
        "تهدف الوساطة إلى التسوية الودية للخلافات بين مؤسسات الائتمان وزبنائها.",
    ),
    Fact(
        "mediation-rules",
        "mediation",
        ("organization",),
        (m(2),),
        "Les documents constitutifs précisent l’objet, la gouvernance, les ressources et le fonctionnement du dispositif ; son règlement fixe la saisine et le traitement.",
        "تحدد الوثائق التأسيسية غرض الآلية وحكامتها ومواردها وكيفية عملها، ويحدد نظامها الإحالة عليها والمعالجة.",
    ),
    Fact(
        "mediation-mandate",
        "mediation",
        ("mandate",),
        (m(3),),
        "Le médiateur présente des garanties d’honorabilité et d’impartialité et des compétences juridiques et financières. La durée du mandat dépend des documents constitutifs ; cet article ne donne pas de durée chiffrée.",
        "يقدم الوسيط ضمانات النزاهة والحياد وكفاءات قانونية ومالية. وتحدد الوثائق التأسيسية مدة الانتداب دون أن تذكر المادة مدة رقمية.",
    ),
    Fact(
        "mediation-secrecy",
        "mediation",
        ("confidentiality",),
        (m(4),),
        "Les personnes participant au traitement respectent un code d’éthique garantissant impartialité et indépendance, ainsi que la confidentialité et le secret professionnel.",
        "يحترم المشاركون في المعالجة ميثاقاً أخلاقياً يضمن الحياد والاستقلال، ويلتزمون بالسرية والكتمان المهني.",
    ),
    Fact(
        "mediation-deadline",
        "mediation",
        ("response_deadline", "extension"),
        (m(5),),
        "Pour une demande jugée recevable, le traitement ne peut dépasser trente jours ouvrés. Si des circonstances justifient une prorogation, le médiateur informe les parties concernées.",
        "بالنسبة إلى طلب مقبول، لا تتجاوز المعالجة ثلاثين يوم عمل. وإذا بررت ظروف تمديد الأجل، يُخبر الوسيط الأطراف المعنية.",
    ),
    Fact(
        "mediation-access",
        "mediation",
        ("procedure",),
        (m(6),),
        "Le client ou l’établissement peut engager la médiation. Pour une demande du client, le grief doit avoir été instruit sans succès par l’établissement concerné.",
        "يمكن للزبون أو المؤسسة بدء الوساطة. وبالنسبة إلى طلب الزبون، يجب أن تكون المؤسسة قد درست موضوع تظلمه دون نجاح.",
    ),
    Fact(
        "mediation-admissibility",
        "mediation",
        ("admissibility",),
        (m(7),),
        "Le médiateur dispose de dix jours ouvrés pour statuer sur la recevabilité. Un refus doit être motivé et accompagné d’une information sur les voies de recours.",
        "يتوفر الوسيط على عشرة أيام عمل للبت في القبول. ويجب تعليل الرفض وإرفاقه بمعلومات عن سبل الطعن.",
    ),
    Fact(
        "mediation-outcome",
        "mediation",
        ("outcome",),
        (m(8),),
        "L’accord transactionnel est écrit et signé par le médiateur, le client et l’établissement. En cas d’échec, un procès-verbal constate la position de chaque partie.",
        "يكون اتفاق الصلح مكتوباً ويوقعه الوسيط والزبون والمؤسسة. وعند الفشل، يثبت محضر موقف كل طرف.",
    ),
    Fact(
        "law-complaint-duty",
        "complaints",
        ("obligation",),
        ("law:157",),
        "L’article 157 prévoit un dispositif interne efficace et transparent de traitement des réclamations, adapté à l’établissement, et renvoie à une circulaire pour ses modalités.",
        "تنص المادة 157 على آلية داخلية فعالة وشفافة لمعالجة الشكايات ملائمة للمؤسسة، وتحيل تحديد كيفياتها إلى دورية.",
    ),
    Fact(
        "law-mediation-duty",
        "mediation",
        ("obligation",),
        ("law:158",),
        "L’article 158 impose l’adhésion des établissements de crédit à un dispositif de médiation bancaire pour régler à l’amiable leurs litiges avec leurs clients.",
        "تفرض المادة 158 انخراط مؤسسات الائتمان في آلية وساطة بنكية للتسوية الودية لخلافاتها مع زبنائها.",
    ),
    Fact(
        "law-bam-recourse",
        "complaints",
        ("bam_recourse",),
        ("law:159",),
        "Une personne s’estimant lésée par un manquement aux textes visés peut saisir Bank Al-Maghrib. L’article 159 décrit ses moyens d’examen, sans prévoir de décision automatique favorable.",
        "يمكن لمن يعتبر نفسه متضرراً من مخالفة النصوص المعنية اللجوء إلى بنك المغرب. وتبيّن المادة 159 وسائل فحص الطلب دون تقرير نتيجة تلقائية لصالح صاحبه.",
    ),
]
