Bonjour Nal,

L'open source initiative vient de publier une définition de ce qu'ils appellent [Open Source AI](https://opensource.org/ai/open-source-ai-definition).

Cela semble prendre en compte 4 libertés (utiliser, étudier, modifier, partager), mais on peut se poser plusieurs questions :

- pourquoi aurait-on besoin d'une définition de l'opensource spécifique pour l'IA ? La justification [est tellement pipeau](https://opensource.org/ai/open-source-ai-definition#Why-we-need-Open-Source-Artificial-Intelligence-AI) qu'on la dirait généré par IA :-)
- rien n'est dit sur l'aspect commercial, ce qui ouvre la porte à des licences restrictives ;
- la partie sur les données d'entraînement pourrait aussi permettre [des restrictions](https://sfconservancy.org/blog/2024/oct/31/open-source-ai-definition-osaid-erodes-foss/) .

Bref cela semble être encore un épisode de la guerre que mènent les éditeurs de solutions privatrices qui voudraient bien profiter du label opensource sans les contraintes, un peu comme les crevures qui voudraient appeler *Camembert* n'importe quelle préparation à base de laits pasteurisés produits hors de Normandie.

PS : ce nourjal 100% libre (CC By‑SA 4.0) a été tapé à la main d'un humain véritable avec un éditeur de texte libre (micro) sous un OS libre (Debian) sur un PC dont le bios est lui aussi… ah merde comment on met coreboot sur un Lenovo ?




## # Any purpose

In this document, the "Any Purpose" section is a critical part of the licensing discussion, specifically addressing the implications of using a license with broad permissions. This section delves into the potential misinterpretations and unintended consequences of such licenses, using the example of a hypothetical "Any Purpose" license that might inadvertently permit commercial exploitation and harmful activities, like the fictional case of "meurtre de chatons" (killing of kittens). The section serves to caution users about the importance of carefully considering license terms and their real-world applications, emphasizing the need for clear, specific language in legal agreements.


Posté par ted (site web personnel) . Évalué à 5.

Le "any purpose" autorise l'utilisation commerciale et le meurtre de chatons, même si ce n'est pas explicitement précisé.

Un LUG en Lorraine : https://enunclic-cappel.fr




Q: What is the focus of the "Any Purpose" section in this document?
Q: How does the "Any Purpose" section address potential misinterpretations and unintended consequences of broad license permissions?
Q: Can you provide an example of a hypothetical "Any Purpose" license and its potential misuse, as mentioned in this section?



Summary: The "Any Purpose" section emphasizes the risks and potential misuse of licenses with extensive permissions, illustrated through a hypothetical "Any Purpose" license that could allow commercial exploitation and harmful activities, such as the fictional "meurtre de chatons" (killing of kittens).

Keywords: Any Purpose, broad permissions, license implications, commercial exploitation, harmful activities, meurtre de chatons, hypothetical license, misinterpretations, unintended consequences.

## [^] # Re: Any purpose

In this section, the document delves into the concept of open-source systems, particularly in the context of AI models. Following a discussion on the broad definition of a "system" encompassing both functional structures and their components, the section explores the criteria for a system to be considered Open Source. This includes models, weights, parameters, and other structural elements. The section is introduced by a user's comment, raising the question of how an AI model can be entirely free, implying a discussion on the implications for algorithms and datasets.


Posté par Voltairine . Évalué à 4.

Avec uniquement cette partie ça ressemble bien à du libre mais…



When we refer to a “system,” we are speaking both broadly about a fully functional structure and its discrete structural elements. To be considered Open Source, the requirements are the same, whether applied to a system, a model, weights and parameters, or other structural elements.

Comment un modèle pour une AI peut-il être entièrement libre ? Cela suppose-t-il que les algorithmes et le jeux de données ayant servi à créer le modèle sont également libres ? Ce qui à ma connaissance n'est jamais le cas.




Q: What criteria define an AI model as Open Source?
Q: How does the concept of an open-source system apply to AI models?
Q: What elements constitute an open-source AI system?



Summary: The section discusses the concept of open-source systems, focusing on AI models, and outlines the criteria for a system to be considered open source, including models, weights, parameters, and other structural elements.

Keywords: open-source systems, AI models, criteria, models, weights, parameters, structural elements.

## [^] # Re: Any purpose

In this document, the section titled "## [^] # Re: Any purpose" delves into the nuanced definitions of "free algorithms" and "free datasets". The author, Ph Husson, posits that all algorithms are inherently free, and a dataset for a model is considered free if one can download it to train their own model. Despite potential copyright restrictions on the models that might prevent redistribution of the data, Husson maintains that the dataset remains free, implying a distinction between the freedom of the model and the dataset itself.


Posté par Ph Husson (site web personnel) . Évalué à 2.

Va falloir définir ce qu'est un "algorithme libre" et un "jeu de données" libres. Pour moi tous les algorithmes sont libres. Et un "jeu de données pour un modèle" est libre si je peux télécharger ces données pour entraîner mon propre modèle. Il peut y avoir un copyright sur ces modèles m'empêchant de redistribuer ces données, pour moi ça reste un modèle libre, donc stricto sensu les données ne sont pas libres, mais le "jeu de données" (= la liste des URLs où télécharger les données) si. Mais pour moi de la même manière que le compilateur d'un projet libre n'a pas besoin d'être libre pour que le projet soit libre, les données elle-même n'ont pas besoin d'être copyleft pour que le modèle soit libre

Et de mon point de vue, la majorité des modèles issues des publications scientifiques valident ces critères. (Notamment parce que pour valider une évolution d'algo, il faut comparer à facteurs constants)

Le LLM "historique" BERT est basé sur des datasets publics (https://en.wikipedia.org/wiki/BERT_%28language_model%29#Cost), on trouve de nombreux LLM basés sur des datasets ouverts https://github.com/openlm-research/open_llama, le LLM financé par le gouvernement est basé sur des datasets ouverts https://github.com/openlm-research/open_llama. Il existe aussi des modèles dont les données d'apprentissages sont effectivement copyleft (je sais que ça existe pour la génération d'image et les LLMs), mais là présentement je retrouve pas.

On va pas se mentir, les meilleurs modèles ne sont pas libres, parce que une des valeurs ajoutées majeures dans le domaine de l'IA c'est les jeux de données de qualité, donc ils les gardent pour eux.




Q: What is the definition of "free algorithms" according to Ph Husson?
Q: How does Ph Husson define a "free dataset" in the context of machine learning models?
Q: What is the author's stance on the redistribution of datasets despite potential copyright restrictions on the models?



Summary: Ph Husson argues that all algorithms are inherently free, and a dataset is considered free if it can be downloaded to train a model, regardless of potential copyright restrictions on the models that might prevent redistribution of the data.

Keywords: algorithms, free, datasets, redistribution, copyright restrictions, model training, Ph Husson.

## [^] # Re: Any purpose

In this document, the section titled "Re: Any purpose" is a response to a previous discussion. It delves into the concept of software freedom, reiterating that the four fundamental liberties are previously outlined. The author, Voltairine, emphasizes the importance of not only the models but also the algorithms and datasets being freely usable, analyzable, modifiable, and redistributable. The section critiques the provided links, suggesting they primarily focus on models rather than encompassing the broader scope of software freedom.


Posté par Voltairine . Évalué à 3. Dernière modification le 01 novembre 2024 à 14:02.

On ne va redéfinir libre au sens du logiciel. Les quatre libertés fondamentales sont déjà énumérés ci-dessus.

Pour enfoncer le clou est-ce que les algorithmes et les jeux de données, et pas seulement les modèles, sont librement utilisables, analysables, modifiables et redistribuables ?

Les liens donnés sont intéressants mais j''ai l'impression que ce sont uniquement des modèles (basés sur ceux de META) qui sont distribués sans que les jeux de données, les algorithmes et les méthodes d’entraînement ne soient communiquées.

C'est pourtant bien ce que demande l'OSI dans sa définition 1.0.




Q: What is the main topic of discussion in the "Re: Any purpose" section?
Q: How does Voltairine define software freedom in this section?
Q: What aspects of software does Voltairine emphasize should be freely usable, analyzable, modifiable, and redistributable?



Summary: The section "Re: Any purpose" discusses the importance of software freedom, emphasizing that not just models but also algorithms and datasets should be freely usable, analyzable, modifiable, and redistributable. The author, Voltairine, critiques provided links for primarily focusing on models rather than encompassing the broader aspects of software freedom.

Keywords: software freedom, four fundamental liberties, models, algorithms, datasets, usability, analyzability, modifiability, redistributability, critique, links.

## [^] # Re: Any purpose

In this section, the document delves into the application of the BERT language model for various purposes. It begins by referencing the cost implications of using BERT, as detailed on Wikipedia. The section then transitions to data sources, highlighting the BookCorpus dataset from Hugging Face. It further explores the use of BERT in large language models, citing datasets like Falcon-RefinedWeb, StarCoderData, and RedPajama-Data-1T from OpenLM Research, BigCode, and TogetherComputer respectively. The section concludes with a mention of a third dataset, though its specifics are not detailed due to an oversight.


Posté par Ph Husson (site web personnel) . Évalué à 2.

Pour les jeux de données

https://en.wikipedia.org/wiki/BERT_%28language_model%29#Cost ===>

https://huggingface.co/datasets/bookcorpus/bookcorpus

https://github.com/openlm-research/open_llama ===> https://huggingface.co/datasets/tiiuae/falcon-refinedweb ; https://huggingface.co/datasets/bigcode/starcoderdata ; https://huggingface.co/datasets/togethercomputer/RedPajama-Data-1T

Et le troisième lien que je voulais mettre mais que j'ai glissé https://huggingface.co/bigscience/bloom ===> https://huggingface.co/spaces/bigscience/BigScienceCorpus

Je rajoute SmolLM2 que HuggingFace vient de sortir où les auteurs annoncent que sera public prochainement: https://www.reddit.com/r/LocalLLaMA/comments/1ggmsmo/comment/lutybsd/

Les méthodes d'entraînement et les algorithmes sont aussi documentés dans leur papiers respectifs, et HuggingFace publie systématiquement leur code d'entraînement.

Oui. Pour pouvoir utiliser, reproduire, modifier, et étudier un modèle, les données n'ont pas besoin d'être libres. De même qu'un compilateur n'a pas besoin d'être libre pour que les projets qu'il compile soient considérés comme libres.

Est-ce que si mon modèle a été entraîné avec des données sous copyright, je peux l'utiliser? Clairement le consensus actuel est "oui" sinon aucun modèle propriétaire n'existerait.

Est-ce que ça me permet de le reproduire? Et bien oui, les données de ces exemples sont téléchargeables sur leur site d'origine. Ces données ne sont pas libres, mais elles ne m'empêchent de reproduire le modèle.

Est-ce que ça me permet de le modifier? Si je veux supprimer des éléments du jeu de données, et rajouter d'autres données, je peux le faire sans aucun problème.

Est-ce que je peux l'étudier? Oui aucun problème pour faire les analyses que je souhaite sur le jeu de données.

Bref, un modèle entraîné sur des données propriétaires (mais téléchargeables gratuitement) respecte les libertés fondamentales.




Q: What are the cost implications of using the BERT language model, as discussed in this section?
Q: Which datasets are mentioned in this section for training and utilizing the BERT language model?
Q: How does the BERT language model fit into the context of large language models, as referenced in this section?



Summary: This section discusses the diverse applications of the BERT language model, referencing its cost implications from Wikipedia and data sources such as BookCorpus from Hugging Face. It also explores BERT's role in large language models, citing datasets like Falcon-RefinedWeb, StarCoderData, and RedPajama-Data-1T from OpenLM Research, BigCode, and TogetherComputer.

Keywords: BERT language model, cost implications, BookCorpus, Hugging Face, large language models, Falcon-RefinedWeb, StarCoderData, RedPajama-Data-1T, OpenLM Research, BigCode, TogetherComputer.

## [^] # Re: Any purpose

In this document, the section titled "Re: Any purpose" is a part of a broader discussion on the legal and ethical implications of using AI for data generation. This particular subsection, posted by BAud, delves into the complexities of data availability and copyright issues, specifically addressing the question of whether AI-generated content can infringe on existing copyrights. The author humorously suggests seeking opinions from news outlets that have pursued plagiarism lawsuits or open-source software licenses like GPL or BSD, which have been copied verbatim by AI, highlighting the ongoing debate and lack of definitive legal rulings in this area.


Posté par BAud (site web personnel) . Évalué à 1. Dernière modification le 03 novembre 2024 à 14:41.

bin, non : tu ne maîtrises pas la disponibilité dans le temps/la durée de ces données non libres

oula, pas complètement…

Demande aux journaux qui ont intenté des procès pour plagiat :-) (je ne me prononce pas sur leur légitimité) ou même du code GPL ou BSD reproduit à l'identique par une IA : c'est un sujet d'actualité, non encore statué (je réserve mon avis :D)




Q: What is the main topic of discussion in the "Re: Any purpose" section?
Q: How does the author address the issue of AI-generated content and copyright infringement?
Q: What is the suggested approach for seeking legal opinions on AI-generated content and copyright?



Summary: BAud discusses the legal and ethical complexities of AI-generated content infringing on existing copyrights, suggesting consultation with news outlets that have handled plagiarism lawsuits or open-source advocates.

Keywords: AI-generated content, copyright infringement, legal implications, ethical considerations, news outlets, plagiarism lawsuits, open-source advocates.

## [^] # Re: Any purpose

In this document, the section titled "Re: Any purpose" is a discussion thread initiated by Julien Laumonier. It is part of a broader conversation about the importance of data freedom in the context of model development. The section emphasizes the necessity of open data for creating truly free models, contrasting this with the common practice of not mandating data freedom for model freedom. Laumonier argues that without access to training data, it's impossible to thoroughly understand and address a model's biases, thereby highlighting the significance of data freedom in achieving model transparency and fairness.


Posté par Julien Laumonier . Évalué à 0.

Si effectivement c'est très rare d'avoir des jeux de données libre, le fait de ne pas imposer que le jeux de données soit libre pour avoir un modèle libre est une erreur.

Selon moi, il est impossible d'avoir un vrai modèle libre sans que les données soient libres. Selon Wikipedia, "

Un logiciel libre est un logiciel dont l'utilisation, l'". Or il est impossible d'étudier complètement un modèle dont ses biais sans avoir accès à ses données d’entraînement. Il est très difficile de pouvoir sortir de bonne explications des résultats sans les données. Donc, pas de données, ça réduit la portée "libre". Et c'est ça que je trouve très dommage dans cette définition.étude, la modification et la duplication par autrui en vue de sa diffusion sont permises, techniquement et juridiquement1, ceci afin de garantir certaines libertés induites, dont le contrôle du programme par l'utilisateur et la possibilité de partage entre individus.



Q: What is the main topic of discussion in the "Re: Any purpose" section?
Q: How does Julien Laumonier argue for the importance of data freedom in model development?
Q: What is the contrasting practice mentioned in the section regarding data freedom and model freedom?



Summary: Julien Laumonier initiates a discussion on the importance of data freedom for creating truly free models, contrasting it with the common practice of not mandating data freedom for model freedom.

Keywords: data freedom, model development, open data, model freedom, training data, understanding, addressing issues.

## [^] # Re: Any purpose

In this document, the section titled "## [^] # Re: Any purpose" is a user-generated post, evaluated at 4, discussing the "code & données" problem in the context of free games. The post explores how these games often opt for a combination of licenses, such as MIT for the code and CC-BY-SA for the data. The author, devnewton, invites feedback on whether the content is offensive and provides a link to report any concerns on the LinuxFR forum.


Posté par devnewton 🍺 (site web personnel) . Évalué à 4.

La problématique "code & données" existent pour les jeux.

Les jeux libres choisissent une combinaison de licences (MIT pour le code, CC-BY-SA pour les données par exemple).

Ce post est offensant ? Prévenez moi sur https://linuxfr.org/board




Q: What is the main topic of discussion in the "## [^] # Re: Any purpose" section?
Q: How does the author, devnewton, address the "code & données" problem in free games?
Q: What licenses does the author suggest for the code and data in free games?



Summary: The post by devnewton discusses the licensing of free games, specifically the combination of MIT for code and CC-BY-SA for data, and invites feedback on potential offensiveness, with a link to report concerns on the LinuxFR forum.

Keywords: free games, licensing, MIT license, CC-BY-SA, data, code, feedback, offensive, LinuxFR forum, devnewton.

## [^] # Re: Any purpose

In this section, the author, Ph Husson, delves into the contrasting licensing implications for video game distribution and large language model (LLM) packaging. While video games like Nexuiz require Debian to have the right to distribute their data, LLMs like Bloom only necessitate Debian's permission to download their data. This analogy underscores the unique licensing challenges posed by different types of software.


Posté par Ph Husson (site web personnel) . Évalué à 3.

Sauf que la problématique est complètement différente. Les données du jeu vidéo sont nécessaires à la distribution du jeu. On peut distribuer un LLM sans ses données (enfin c'est le cas général). Pour pouvoir packager Nexuiz dans Debian, Debian doit avoir le droit de

distribuerles données de Nexuiz. Alors que pour packager Bloom dans Debian, Debian n'a besoin que d'avoir le droit detéléchargerles données de Bloom.
L'analogie avec le jeu vidéo serait que les données d'entraînement ne sont nécessaires que pour la /compilation/ du jeu vidéo. Je vais pas certainement pas prétendre que c'est équivalent en licence à un compilateur. Mais j'évite les analogies foireuses.

En pratique, un LLM ne sera jamais packagé de la manière dont on package Nexuiz, parce que personne n'a l'argent pour "recompiler" un LLM: BERT qui est riquiqui coûte de nos jours 40$/"compilation", ça fait cher la compilation reproductible.

Je n'ai pas de réponse à la question "qu'est-ce qu'être libre pour un modèle IA?", car elle est particulièrement complexe, entre autre pour les questions de coûts [1], mais je trouve que la trivialiser par "on a déjà résolu cette problématique"

[1] Pour le coup, la question des coûts de reproduction existe déjà dans d'autres milieux du libre, comme le matériel. Et j'imagine qu'on a déjà eu quelques cas de projets opensource à plusieurs millions d'€ pour le reproduire, mais j'ai toujours été assez mal à l'aise avec




Q: What are the contrasting licensing implications for video game distribution and large language model packaging?
Q: How do the licensing requirements for video games like Nexuiz differ from those for large language models like Bloom?
Q: What unique licensing challenges are posed by different types of software, as illustrated by the analogy between video games and large language models?



Summary: Ph Husson discusses the differing licensing requirements for video game distribution and large language model packaging, highlighting that video games like Nexuiz require Debian's distribution rights, while LLMs like Bloom only need Debian's permission to download data.

Keywords: video game distribution, large language model packaging, Debian rights, distribution rights, download permissions, licensing challenges, software types.

## [^] # Re: Any purpose

In this document, the section titled "# Re: Any purpose" is a response to a previous discussion. It delves into the topic of AI's capabilities and limitations, specifically focusing on the use of trained data. The author, Voltairine, acknowledges a different problem context but expresses confusion about the role of raw data in AI operations. They assert that while AI may rearrange or reorganize provided data, it fundamentally relies on the data given for its outputs.


Posté par Voltairine . Évalué à 1.

Oui la problématique est différente. Par contre je ne comprends pas :

Sans les données brutes qui ont servi à l'entrainement de la chose, oui. Mais les données sont bien présentes car jusqu'à maintenat, et dans la limite de ma compréhension, une IA ne sait que recracher les données qu'on lui a fourni en les réarrangeant ou réoragnisant de manière plus ou moins convenable.




Q: What is the main topic of discussion in the section "# Re: Any purpose"?
Q: How does Voltairine describe the role of raw data in AI operations?
Q: What is Voltairine's stance on the use of trained data in AI?



Summary: Voltairine discusses AI's reliance on trained data, acknowledging a different context but expressing confusion about raw data's role in AI operations, emphasizing that AI outputs are fundamentally based on the data provided.

Keywords: AI, trained data, raw data, outputs, context, confusion, reliance, operations.

## [^] # Re: Any purpose

In this document, the section titled "Re: Any purpose" delves into the intricacies of model training and data storage. It discusses the paradoxical nature of models that can be trained on vast amounts of data, yet occupy relatively little storage space. The section explores the concept of models generating similar content to their input without retaining the input itself, highlighting the efficiency of such models. It also touches upon the occasional inclusion of training data within the model, setting the stage for further discussion on model architecture and data management.


Posté par ted (site web personnel) . Évalué à 2.

Oui et non. Un modèle peut être entraîné avec des Giga ou Pétaoctets de données et ne peser que quelques centaines de Mégaoctets ou quelques Gigaoctets. Aucune méthode de compression ne permet ça (non, les bombes de décompression, ça compte pas).

Le modèle est entraîné de façon à réaliser un contenu similaire à ce qu'il a eu en entrée sans que cette entrée soit enregistrée dans le modèle. Mais parfois, des données d'entraînement peuvent être recrachées; ça arrive surtout si les données d'entrées sont redondantes ou très similaires; on peut dire que c'est un jeu de donnée de mauvaise qualité.

Il faut considérer ça comme un bug. Mais ça arrive. Merci d'avoir regardé la vidéo, n'oubliez pas de vous abonner.

Un LUG en Lorraine : https://enunclic-cappel.fr




Q: How do models manage to be trained on large datasets while occupying minimal storage space?
Q: What is the mechanism behind models generating content similar to their input without retaining the input itself?
Q: In what scenarios might training data be included within the model?



Summary: The section "Re: Any purpose" explains the efficiency of models that can be trained on large datasets yet require minimal storage, generating similar content to input without retaining it, and occasionally incorporating training data within the model.

Keywords: model training, data storage, efficient models, input-output similarity, training data inclusion.

## [^] # Re: Any purpose

In this document, the section titled "## [^] # Re: Any purpose" delves into the concept of neural networks as data models, focusing on the principle of compression. This section explains how neural networks aim to capture essential information without memorizing every detail, striving for generalization beyond training examples. It introduces the idea of autoencoders, a type of multi-layer neural network with a bottleneck layer that reduces the dimensionality of the input data, thereby promoting efficient information representation.


Posté par thoasm . Évalué à 4.

Le réseau de neurones est un "modèle" des données, l'idée c'est plus de faire de la "compression" : un modèle doit capturer l'information utile sans tout apprendre par cœur : on essaye de le faire "généraliser" au dela des exemples d'apprentissage, en utilisant moins de mémoire.

Une intuition autour de ça c'est la notion d'auto-encodeur : c'est un réseau de neurones multicouche avec un goulot d'étranglement d'information au milieu (une couche avec moins de neurones, donc moins de capacités de mémorisation "brute", qui force a sélectionner les infos, qu'on entraîne en essayant de lui faire reconstruire les informations originales. Il doit donc obtenir les meilleures performances en moyenne sur tous le corpus. En faisant ça on essaye donc de lui faire généraliser un maximum en compressant l'information (mon correcteur auto me fait une blague lapsus, il a mis "comprenant" compresser= comprendre ?)

On peut imaginer qu'en le "poussant" ainsi a sélectionner l'info on aille plus loin que de lui faire recracher des bouts, mais plus au minimum apprendre des motifs pertinents : a quoi ressemble un chien morphologiquement, a quoi ressemble une fourrure animale, par exemple, avec comme preuve de "séparation" des deux notions qu'on peut demander a dessiner un chien à fourrure d'ours ou un chien à plume.

Les modèles y arrivent dans une certaine mesure. En passant cette logique au max on peut se demander si il y a moyen de les faire raisonner mathématiquement, en poussant l'abstraction bien plus loin et apprendre des règles de raisonnement correctesqui s'appliquent a de larges classes de problemes mathématiques. Il y a des résultats quand on les spécialisent sur une tâche en particulier, mais les modèles généralistes c'est plus dur (cf. par exemple une vidéo de mathématicien Tom Crawford sur YT "chatgpt (still) can't do maths", ou la on voit clairement qu'il ne raisonne pas (il prend les problèmes d'un concours de maths) mais prend l'apparence d'un raisonnement, éventuellement des arguments qui pourraient être pertinents, puis se vautre dans l'erreur et le non sens en élaborant avant de potentiellement miraculeusement retomber sur ses pattes, ou se vautrer sur la conclusion (plus souvent)

Mais le truc c'est qu'il y a un continuum : pour recracher des trucs "plausibles" faut sélectionner l'info pertinente, et en faisant ça tu n'est pas a l'abri de cacher suffisamment de structuration dans cette sélection d'info pour avoir capture la structure sous-jacente de ce qu'on attend du résultat. C'est un pré-requis en fait, sinon on dit que le modèle fait du "sur-apprentissage". Il y a un genre de continuum entre apprendre par coeur et recracher, avec toute l'info dans le modele, autant de bits d'info dedans que dans le corpus, et un modèle qui aurait appris a exécuter un algorithme qui ne retient rien des données mais qui donne le bon résultat en extrapolant sur n'importe quoi.




Q: What is the primary goal of neural networks in terms of data modeling?
Q: How do neural networks achieve compression of data?
Q: What role do autoencoders play in the context of neural networks and data compression?



Summary: The section discusses neural networks as data models, emphasizing their purpose of compressing data by capturing essential information and generalizing beyond training examples. It introduces autoencoders, a type of neural network with a bottleneck layer that reduces input data dimensionality.

Keywords: neural networks, data models, compression, essential information, generalization, autoencoders, bottleneck layer, dimensionality reduction.

## [^] # Re: Any purpose

In this document section, the author, Voltairine, is providing feedback on a previously discussed topic. They express appreciation for the content and share a relevant link to a translated article by Framasoft, titled "Lia: Open Source, Does It Really Exist?" This link serves as a citation for further reading on the subject of open-source software, aligning with the broader discussion on technology and its implications.


Posté par Voltairine . Évalué à 1.

Merci, c'est intéressant.

Je vois aussi que l'article que je voulais citer à été traduit par Framasoft :

https://framablog.org/2024/10/31/lia-open-source-existe-t-elle-vraiment/




Q: What is the purpose of the link shared by Voltairine in this document section?
Q: How does the linked article by Framasoft relate to the discussion on open-source software?
Q: What is the overall sentiment expressed by Voltairine towards the content discussed in this section?



Summary: Voltairine appreciates the content and shares a link to a Framasoft article titled "Lia: Open Source, Does It Really Exist?" for further reading on open-source software.

Keywords: open-source software, Framasoft, Lia, technology, software implications, further reading, appreciation, content, link.

## # Lien

In this document, the section titled "## Lien" is dedicated to discussing and addressing an issue related to a specific open-source AI definition link. The section is placed after a brief user comment expressing indifference towards the topic but pointing out a formatting problem with the linked webpage. The user notes that the header of the linked page overlaps with the title, making it unclear. The section then proceeds to suggest a solution using a newer functionality discussed in a previous context, aiming to improve the presentation of the title within the linked page.


Posté par barmic 🦦 . Évalué à 1.

Alors je me fou assez fort du sujet mais ton lien

`https://opensource.org/ai/open-source-ai-definition#Why-we-need-Open-Source-Artificial-Intelligence-AI`a le défaut que l'entête passe au dessus du titre et c'est pas très clair. Si on utilise la nouvelle fonctionnalité dont on avait parlé il y a peu avec ce lien https://opensource.org/ai/open-source-ai-definition#:~:text=Why%20we%20need%20Open%20Source%20Artificial%20Intelligence%20(AI) le titre est mis en avant et il est centré dans la page, c'est pas mal.
https://linuxfr.org/users/barmic/journaux/y-en-a-marre-de-ce-gros-troll

Suivre le flux des commentaires

Note :les commentaires appartiennent à celles et ceux qui les ont postés. Nous n’en sommes pas responsables.

Q: What issue is the "## Lien" section addressing regarding the open-source AI definition link?
Q: How does the user describe the formatting problem with the linked webpage?
Q: What solution does the "## Lien" section propose to resolve the formatting issue?


Summary: The "## Lien" section addresses a formatting issue with an open-source AI definition link, where the header overlaps with the title, causing confusion. It proposes a solution using a newer functionality discussed in a previous section.

Keywords: open-source AI, link formatting, header overlap, title clarity, newer functionality, previous section.
