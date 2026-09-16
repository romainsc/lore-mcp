# Reproducibility is the New Copyleft:

In this section, we delve into the innovative concept of "Reproducibility is the New Copyleft," a paradigm shift in ensuring user freedom and transparency, particularly in the context of Artificial General Intelligence (AGI). This discussion builds upon the historical precedent set by copyleft licenses like the GNU General Public License, which leveraged copyright law to mandate source code availability during distribution. Here, we explore the implications of this legacy, focusing on the technical underpinnings that enabled copyleft's effectiveness: the reproducible relationship between source code and object code. We then extend this analysis to the emerging field of AGI, proposing a novel approach that leverages reproducibility as a cornerstone for safeguarding user rights and fostering transparency in AGI development.


Defining AGI-oriented Reproducible Builds

###### Abstract

The concept of *copyleft*, as implemented in licenses such as the GNU General Public License, was a legal hack that used copyright to guarantee user freedom by tying the availability of source code to every act of distribution. Its normative force rested on an implicit technical premise: that source code and object code stand in a well-defined, humanly auditable, and reproducible relationship. Large language models and, prospectively, Artificial General Intelligence (AGI) systems systematically violate this premise. The training artifacts jointly required to reconstruct a given model—code, data, weights, hyperparameters, toolchain, and hardware configuration—are each subject to independent legal, technical, and economic constraints that no current open-source framework fully resolves. Sufficiently capable AI systems can also *rewrite* licensed source into functionally equivalent derivatives stripped of their original obligations, a form of laundering against which copyleft has no effective defense.

This paper argues that a functional analogue of copyleft for AGI must be grounded not in share-alike clauses over code, but in *reproducible builds*: a practice guaranteeing bit-exact reconstructability from declared inputs. We review the history and logic of copyleft, critically examine Maffulli’s *Second Liberation* thesis according to which AI fulfills Stallman’s dream, and show that the argument collapses unless AGI systems are themselves reproducible. Drawing on the Open Source AI Definition (OSAID), the Model Openness Framework (MOF), OpenMDW, and deterministic-inference research by Thinking Machines Lab, SGLang, and others, we define seven requirements for *AGI-oriented reproducible builds*. We further argue that the Model Context Protocol (MCP) and analogous AI-to-AI coupling mechanisms constitute a new *dynamic linking layer* for which copyleft-style licensing is ill-suited, and that Masnick’s “protocols, not platforms” framework offers a more promising governance template for the AI linking layer.

###### Keywords:

Copyleft Reproducible Builds Open Source AI AGI Data Governance OSAID MCP Protocol Governance



Q: What is the concept of "Reproducibility is the New Copyleft"?
Q: How does this concept ensure user freedom and transparency, especially in the context of Artificial General Intelligence (AGI)?
Q: How does the legacy of copyleft licenses like the GNU General Public License influence this new paradigm?



Summary: The section introduces the idea of "Reproducibility is the New Copyleft," a modern approach to safeguarding user freedom and transparency, especially in Artificial General Intelligence (AGI). This concept draws inspiration from copyleft licenses, which used copyright law to ensure source code availability during distribution.

Keywords: Reproducibility, Copyleft, Artificial General Intelligence (AGI), user freedom, transparency, source code availability, copyright law, paradigm shift, tech innovation.

## 1 Introduction

In this document, the section titled "1 Introduction" serves as the opening segment, setting the stage for the subsequent discussion on advanced artificial intelligence governance. It briefly outlines the dual focus of the paper, which is divided into two main strands: the open source AI debate and the AGI safety and governance debate. The former explores the implications of "open" for machine learning systems, while the latter delves into the challenges posed by systems capable of recursive self-improvement or self-replication. This introduction provides a concise overview of the complex policy landscape surrounding AI, positioning the paper as a contribution to this ongoing discourse.


The governance of advanced artificial intelligence has become one of the defining policy questions of the mid-2020s. Within that discussion, two ostensibly distinct strands have evolved largely in parallel: the *open source AI* debate, concerned with the meaning of “open” for machine learning systems that combine code, weights, and data; and the *AGI safety and governance* debate, concerned with systems capable of recursive self-improvement or self-replication [[15](#bib.bib15)]. This paper argues that these strands intersect at a single, surprisingly technical point: the question of what it means for an AI system to be *reproducible*, and whether reproducibility can play the role for AGI that copyleft played for traditional software.

The original copyleft hack, engineered by Richard Stallman in the 1980s, used copyright law to guarantee that every recipient of a GNU program would also receive the source code necessary to study and modify it [[33](#bib.bib33)]. As Maffulli has recently argued [[20](#bib.bib20)], copyleft was in this sense a “permission slip” for freedom rather than its substantive guarantee: the user still needed the skill and the time to exercise the freedoms the license protected. Maffulli’s provocation is that modern AI coding assistants are the real, technical implementation of software freedom—the “second liberation”—because they collapse the knowledge barrier that made the GPL a merely notional promise for non-programmers.

The argument is rhetorically powerful but substantively incomplete. Maffulli himself concedes, in a postscript, that it would be “a lot better if the AI code generators were Open Source AI.” Everything hangs on that “open” qualifier. If the tools supposed to realize software freedom are themselves opaque black boxes run on remote servers, the move has merely replaced one form of vendor tyranny with another.

In an earlier essay [[14](#bib.bib14)], we suggested that the essence of copyleft was not the share-alike clause per se but the *equivalence* it induced between source and object code: because the source had to accompany the binary as the “preferred form for modification,” the binary was in principle always reducible to a human-readable, collaboratively maintainable representation. Generative AI breaks this equivalence. Even when training code is fully released, the weights, training data, preprocessing scripts, random seeds, GPU microcode, and distributed-scheduling decisions jointly determine the resulting model, and no subset of these alone suffices to reconstruct it. The natural technical analogue of copyleft in this setting is the *reproducible builds* methodology: a discipline guaranteeing that a specified set of inputs always produces a bit-identical output, so that any third party can verify the correspondence between a published artifact and its stated sources.

This paper develops that proposal into a set of concrete requirements for AGI systems, but also extends the diagnosis in two directions. First, generative AI creates a new and corrosive problem for copyleft itself: sufficiently capable assistants can *rewrite* GPL-licensed source into functionally equivalent code releasable under any license, collapsing the cost asymmetry on which copyleft’s practical force has always depended. Second, the rapid adoption of the Model Context Protocol (MCP) and similar runtime coupling standards establishes a new *dynamic linking layer* between AI systems, for which the appropriate governance framework is not copyleft at all but the “protocols, not platforms” template developed by Masnick in the social-media context. The paper thus proposes a *two-layer governance architecture*: reproducible builds for the production layer and protocol governance for the linking layer. Making the underlying governance logic of this architecture explicit—a gap that OSAID, MOF, the EU AI Act’s open-source provisions, and the Reproducible Builds project share—is the primary contribution of this paper.




1. Q: What are the two main strands of focus in this document?
2. Q: How does the "open source AI debate" contribute to the discussion in this document?
3. Q: What aspects of AGI safety and governance are explored in this document?



Summary: The "1 Introduction" section introduces the document's focus on advanced artificial intelligence governance, highlighting two main strands: the open source AI debate and the AGI safety and governance debate.

Keywords: advanced artificial intelligence, governance, open source AI debate, AGI safety, recursive self-improvement.

## 2 Copyleft: Definition, History, and Underlying Logic

In this document, Section 2 delves into the concept of Copyleft, a unique approach to copyright licensing. It explores the definition, historical evolution, and the underlying logic of Copyleft. The section begins by explaining how Copyleft employs copyright law in a reverse manner, allowing for copying and modification under the condition that any derivative works also adhere to the same licensing terms. The focus then shifts to the GNU General Public License (GPL), a pioneering and widely recognized implementation of Copyleft, first introduced in 1989 and subsequently updated as GPLv3 in 2007. The section concludes by outlining the four fundamental freedoms encapsulated in the Free Software Definition, which are central to the Copyleft philosophy.


Copyleft is commonly defined as a licensing technique that uses the exclusionary power of copyright in reverse: rather than restricting copying, the license permits copying and modification on the condition that derivative works be distributed under identical terms [[33](#bib.bib33)]. The GNU General Public License (GPL), first released in 1989 and revised as GPLv3 in 2007, is the canonical implementation [[8](#bib.bib8)]. The Free Software Definition codifies four freedoms: to run, to study and modify, to redistribute, and to redistribute modified versions [[9](#bib.bib9)]. Crucially, the freedoms to study and to redistribute modified versions (freedoms 1 and 3 in the FSF’s zero-indexed numbering) are conditioned on “access to the source code” as a *precondition*; the GPL’s share-alike obligation ensures that this precondition propagates along every distribution chain.

What is less often emphasized is the technical premise that makes the Free Software Definition intelligible in the first place. The definition presupposes that *source code* is a well-defined artifact standing in a specific relation to the *object code* that ends up executing on a user’s machine. GPLv3 makes this explicit by defining the “Corresponding Source” as “all the source code needed to generate, install, and … run the object code and to modify the work,” including scripts to control compilation and installation [[8](#bib.bib8)]. The license assumes, in other words, that a deterministic, human-auditable build process converts source into binary, and that obligations attached to the source therefore meaningfully constrain what users can do with the binary.

This is the technical foundation on which the legal structure rests. Copyleft enforces the equivalence of source and object: whatever the user possesses at runtime must be derivable, via a disclosed and reproducible procedure, from the disclosed source. When that equivalence holds, the four freedoms are genuinely actionable; when it fails, the license may still be formally satisfied while the substantive freedoms evaporate. It is this equivalence, rather than share-alike as such, that deserves to be regarded as the normative core of copyleft—and that the present paper takes as its starting point.




Q: What is the definition of Copyleft and how does it utilize copyright law?
Q: How has the concept of Copyleft evolved historically?
Q: What is the underlying logic behind the Copyleft approach to licensing?



Summary: This section discusses Copyleft, a copyright licensing method that uses copyright law in reverse, enabling copying and modification under the condition that derivative works also comply with the same licensing terms. It covers the definition, historical development, and logical basis of Copyleft, with a particular emphasis on the GNU General Public License (GPL).

Keywords: Copyleft, copyright licensing, GNU General Public License (GPL), reverse copyright, derivative works, licensing terms, historical evolution, logical basis.

## 3 The Collapse of Source–Object Equivalence in Modern AI

In this section, we delve into the profound implications of the collapse of source-object equivalence in modern AI, specifically focusing on machine learning systems and large language models. This discussion is pivotal as it challenges the traditional assumption that object code is a direct, deterministic result of a transparent source-code compilation process. We explore how the observable behavior of a trained model is influenced by a complex interplay of factors, including the training code and the training dataset. The training code encompasses a range of elements such as data-loading, tokenization, optimizer, and loss-computation logic, while the training dataset is often a vast, diverse collection of documents from various sources, each with its unique legal and ethical considerations.


Machine learning systems—and above all large language models—systematically violate the assumption that object code is the deterministic output of a disclosed source-code compilation process. A trained model’s observable behavior is jointly determined by at least the following:

1. 1. 
the training code, including data-loading, tokenization, optimizer, and loss-computation logic;
2. 2. 
the training dataset, often composed of billions of documents from heterogeneous sources with varying legal status;
3. 3. 
the set of hyperparameters, including learning rates, batch sizes, dropout probabilities, and seed values;
4. 4. 
the sequence of random numbers actually drawn during training, which depends not only on seeds but on the scheduling behavior of distributed workers;
5. 5. 
the software toolchain, from the deep-learning framework down to CUDA/cuDNN, compiler versions, and floating-point intrinsics;
6. 6. 
the hardware, including the specific GPU microarchitecture, driver, and interconnect topology;
7. 7. 
the model weights produced by the above, typically numbering in the billions and stored in formats whose numerical semantics depend on item 5.

A system that releases only the weights, or only the training code, or only the dataset, does not enable a third party to reconstruct the model. It does not even enable them to verify whether the released weights were in fact produced by the disclosed training procedure. The four freedoms, in the Free Software sense, become unexercisable: one cannot meaningfully study the system’s behavior, modify it in a principled way, or redistribute a known-good version, if none of the claimed inputs can be independently checked.

The Open Source AI Definition (OSAID) promulgated by the Open Source Initiative in October 2024 [[25](#bib.bib25)] explicitly recognizes this problem. The OSAID requires that an open source AI system make available: (i) the complete source code used to train and run the system; (ii) the model parameters, including weights; and (iii) sufficiently detailed *data information* to allow a “skilled person” to build a substantially equivalent system using the same or similar data. The data-information category is the OSAID’s pragmatic compromise with the legal fact that many training corpora cannot be redistributed, whether because they contain personally identifiable information, because they were scraped under text-and-data-mining exceptions that do not extend to redistribution, or because they incorporate copyrighted material [[27](#bib.bib27), [2](#bib.bib2)]. The OSI has continued to refine OSAID and made data governance its central priority for 2025–2026 [[26](#bib.bib26), [28](#bib.bib28)].

This compromise has been controversial. Critics such as the Software Freedom Conservancy have argued that “data information” falls short of the “preferred form for modification” standard that the original Open Source Definition demands, because a substantially equivalent dataset is not the same as the original and the OSAID therefore fails to require reproducibility of the scientific process by which the system was built [[17](#bib.bib17)]. Parts of the Debian community have taken the further view that most models blessed as OSAID-compliant would be ineligible for distribution under the Debian Free Software Guidelines, because their training data is not redistributable as “source” [[17](#bib.bib17)]. The Linux Foundation’s Model Openness Framework (MOF) [[34](#bib.bib34)] and the associated Model Openness Tool [[11](#bib.bib11)] take a different approach, defining three tiers—Open Model, Open Tooling, and Open Science (Class I being the most complete)—with the highest tier demanding raw training datasets, intermediate checkpoints, and log files. OpenMDW, a license issued alongside MOF, is notably *permissive rather than copyleft* [[35](#bib.bib35)]—a design decision that this paper’s argument suggests may need to be revisited for AGI.

What is interesting, for present purposes, is that none of these frameworks guarantees the source–object equivalence that copyleft presupposed for software. Even a Class I (Open Science) MOF release, with all 17 lifecycle components disclosed, cannot by itself ensure that a user rebuilding the model from those components will obtain bit-identical weights. The gap between “all ingredients disclosed” and “system verifiably rebuildable” is precisely where the copyleft analogy has to be reconstructed on a new technical foundation.




Q: What is the significance of the collapse of source-object equivalence in modern AI?
Q: How does the observable behavior of a trained model in AI systems reflect the complex interplay of factors beyond just source-code compilation?
Q: In what ways does the traditional assumption of object code as a direct result of source-code compilation process get challenged in modern AI?



Summary: This section examines the significant impact of the breakdown of source-object equivalence in contemporary AI, particularly in machine learning and large language models, which contradicts the conventional belief that object code is a straightforward, predictable outcome of source code compilation. It highlights the intricate factors influencing a model's observable behavior during training.

Keywords: source-object equivalence, modern AI, machine learning, large language models, training code, observable behavior, complex interplay, factors, deterministic result, transparent source-code compilation.

## 4 Maffulli’s Second Liberation Thesis and Its Limits

In this section, we delve into the implications of Maffulli's Second Liberation Thesis, as presented in his work [[20](#bib.bib20)]. This thesis, a significant contribution to the discourse on the GNU General Public License (GPL), is explored in the context of its historical role in safeguarding users from vendor control. We then transition to the contemporary relevance of this thesis, particularly in light of the emergence of AI code assistants. These tools, by making expertise more accessible, are reshaping the dynamics of software development and the practical application of the right to fork, a cornerstone principle of the GPL.


Maffulli [[20](#bib.bib20)] advances a striking thesis. The GPL, on his reading, was a legal hack that protected users from vendor tyranny but left them dependent on a scarce supply of expert developers to exercise that protection. AI code assistants now democratize that expertise. When a non-programmer can instruct an agent to refactor an abandoned library in an afternoon, the right to fork ceases to be theoretical. Borrowing a framing from Armin Ronacher that Maffulli approvingly cites, software is shifting from a *static monument* maintained by an elite to a *fluid resource* reshapable by any user. In this sense, AI provides the “technical enforcement” of the freedoms that copyleft could protect only legally.

There is much to this. The distinction between formal and substantive freedom is real, and the reduction of the skill premium required to modify code is plainly happening, at least at the margin. Yet the thesis is incomplete in a way that Maffulli himself half-acknowledges: the argument is sound only if the AI tools doing the liberation are themselves open source AI. If the code assistant is a remote API controlled by a single vendor, the user who has formally gained the freedom to fork has in fact acquired a new dependency—the vendor can change the model, withdraw the service, censor refactorings, log codebases, or silently inject behavior the user cannot audit. Widder, West, and Whittaker [[36](#bib.bib36)] argue that the political economy of “open” cloud AI systematically favors concentrated incumbents, and these runtime risks are among its concrete expressions. The substantive freedom the Second Liberation promises is, in such a setting, merely displaced from the maintainer of the upstream library to the operator of the assistant.

A second limitation is epistemic. Even if the model is open-weight and its training code released, a user who relies on the model’s output to reshape software has no way to verify that the model’s behavior was not shaped, during training, by adversarial data or supply-chain attacks. Both training-data extraction [[3](#bib.bib3)] and training-data poisoning [[4](#bib.bib4)] are well-documented attack vectors, and models trained on scraped web-scale corpora offer a particularly large surface for the latter. A user cannot audit a trillion-parameter model by reading it. The only available form of audit is procedural: verify that the claimed inputs produce the claimed outputs. This is exactly the role that copyleft-style source availability once played for ordinary software. The fix for Maffulli’s diagnosed gap is not simply “more powerful AI,” but AI whose construction is as transparently reconstructible as a GPL-licensed compiler.




Q: What is Maffulli's Second Liberation Thesis and how does it relate to the GNU General Public License (GPL)?
Q: How has Maffulli's Second Liberation Thesis historically protected users from vendor control?
Q: What is the contemporary relevance of Maffulli's Second Liberation Thesis, especially in the context of AI code assistants?



Summary: Maffulli's Second Liberation Thesis, discussed in [[20](#bib.bib20)], is examined for its historical significance in protecting users from vendor control under the GNU General Public License (GPL). The thesis's contemporary relevance is also explored, especially in the context of AI code assistants that democratize expertise.

Keywords: Maffulli's Second Liberation Thesis, GNU General Public License (GPL), vendor control, AI code assistants, user protection, expertise democratization.

## 5 The Rewrite Problem: AI as a Copyleft-Laundering Machine

In this section, the document delves into the ethical and legal implications of AI-powered coding assistants, specifically focusing on the potential misuse of these tools for circumventing copyleft licensing requirements. This discussion is part of a broader exploration of the "Rewrite Problem" in the context of AI and software development. The section follows an analysis of Maffulli's Second Liberation, a concept that highlights the benefits of AI in freeing developers from the burden of maintenance. However, it also underscores a more concerning aspect: the possibility of these tools being used to systematically evade the terms of copyleft licenses, thereby undermining the principles of open-source software.


There is a further, and more corrosive, implication of Maffulli’s Second Liberation that Maffulli himself does not draw out. If AI coding assistants can refactor arbitrary codebases on demand, then the same capability that liberates the user from the tyranny of the maintainer also permits the systematic laundering of copyleft obligations. A user who possesses a GPL-licensed library and wishes to incorporate its functionality into a proprietary product need no longer negotiate with upstream, nor reason about the boundary between derivative work and aggregation. They can instruct an AI assistant to produce a functionally equivalent rewrite—clean-room by construction, or at least plausibly defensible as such in court—and release the result under whatever terms they prefer.

This is not merely hypothetical. The most vivid public instance to date is the March 2026 chardet controversy: Dan Blanchard, long-time maintainer of the Python character-encoding library, used an AI coding agent to produce a “ground-up, MIT-licensed rewrite” of the previously LGPL-licensed codebase in roughly five working days, citing standard-library-inclusion requirements and a 48 speedup as motivation. A JPlag analysis reported under 1.3% structural overlap with prior versions [[6](#bib.bib6)]. The library’s original author Mark Pilgrim, returning from more than a decade of public silence, objected that Blanchard’s “ample exposure” to the LGPL codebase over a decade of maintenance made any clean-room defense implausible. Notably, Maffulli himself cites chardet as a paradigmatic illustration of the Second Liberation [[20](#bib.bib20)]; read from the standpoint of this paper, the same event is a paradigmatic illustration of copyleft laundering. Chardet 7.0 represents the first high-profile case in which the engineering conditions for AI-assisted copyleft relicensing have become operational, whatever its eventual legal resolution.11
            1
            
            
            
          At the time of writing, the matter has not entered the litigation record, and the legal question of whether chardet 7.0 is a derivative work of its LGPL predecessors remains unresolved. The claim here is that the engineering and economic conditions now permit such relicensing at a cost the copyleft tradition has never before had to confront—not that such laundering already succeeds as a legal matter. The engineering workflow generalizes straightforwardly: feed the GPL source into the assistant, request a reimplementation in the same language or a different one, perhaps iterate a few times on architectural style, and ship. The resulting code is unlikely to contain substantial verbatim fragments of the original; under the idea/expression dichotomy, copyright protects expression and not the underlying ideas or functionality, leaving such rewrites with limited exposure [[31](#bib.bib31)]. This is not to say that every rewrite is safe: substantial similarity of non-literal elements can still support an infringement claim, and post-*Google v. Oracle* doctrine remains unsettled on the boundary between functional and expressive reimplementation. But the threshold of safety is moving, and moving in favor of the evader. Even where a rewrite might qualify as a derivative work in the statutory sense, enforcement against a large vendor with deep pockets and plausible deniability would be prohibitively costly for most upstream maintainers. The cost of producing such rewrites is collapsing even faster than the cost of writing new code from scratch, because rewriting is a simpler task for current-generation models than greenfield development [[20](#bib.bib20)].

Copyleft was always dependent on a particular economic assumption: that the cost of rewriting a substantial codebase from scratch was high enough to make compliance cheaper than evasion. The GNU Compiler Collection, the Linux kernel, and readline—three canonical examples around which copyleft doctrine developed—are all systems whose reimplementation would historically have required years of skilled engineering labor. Generative AI dissolves this asymmetry. The threshold at which it becomes cheaper to evade copyleft than to comply with it is being pushed downward, library by library: small utility libraries are already well within the cost-effective evasion range, and only the very largest systems, whose complexity resists automated reconstruction, will retain the protection that cost asymmetry once afforded to all of free software. The process is gradual and largely invisible—there is no headline moment at which copyleft “fails”—but its cumulative effect is to strip copyleft of the economic backbone on which its normative force depended.

The implication is direct. A governance regime for AGI-era software cannot rely on share-alike obligations over source code: a source file is no longer a scarce, artisanal artifact whose reproduction requires matching skill, but increasingly a cheap derivative of an expressible specification. What remains scarce—and therefore a plausible target for governance—is the verifiable procedure by which a system of a given behavioral profile came into existence. Crucially, the argument generalizes reflexively: if copyleft cannot meaningfully constrain AI-assisted rewriting of ordinary software, then *a fortiori* it cannot constrain an AGI that rewrites its own training code, data-selection heuristics, or evaluation harness in pursuit of self-improvement. Requirement R6 (recursive verifiability), developed below, is our response to both at once.




Q: What is the "Rewrite Problem" in the context of AI and software development?
Q: How might AI-powered coding assistants be misused to circumvent copyleft licensing requirements?
Q: What is Maffulli's Second Liberation and how does it relate to the discussion on AI and software development?



Summary: The section discusses the ethical and legal concerns surrounding AI-powered coding assistants, particularly their potential misuse for evading copyleft licensing obligations, a phenomenon known as the "Rewrite Problem." This is framed within the context of Maffulli's Second Liberation, which emphasizes the advantages of AI in alleviating developers' workload.

Keywords: AI-powered coding assistants, copyleft licensing, Rewrite Problem, ethical implications, legal implications, Maffulli's Second Liberation, software development, developer workload.

## 6 Reproducible Builds as a New Copyleft

In this section, we delve into the innovative concept of "Reproducible Builds as a New Copyleft" (Section 6). This topic builds upon the long-standing engineering practice within the free software community, which has been refined over a decade. The focus is on the principle of reproducible builds, a methodology that ensures any individual, given the same declared source and toolchain, can generate an identical binary. This section highlights the commitment of projects like Debian, Tails, and NixOS, who have significantly contributed to making their distributions reproducible. The rationale behind this approach is rooted in the belief that a transparent source code can be effectively audited and verified, thereby enhancing trust and security in the software development process.


The free software community has been developing, for over a decade, an engineering practice that addresses exactly this kind of procedural audit: *reproducible builds* [[30](#bib.bib30)]. A build is reproducible if any party, starting from the same declared source and toolchain, obtains a bit-for-bit identical binary. The Debian, Tails, and NixOS projects, among others, have invested substantial effort in making their distributions reproducible; the motivation is that a disclosed source code cannot protect the user from a compromised build server unless the correspondence between source and binary can be independently checked [[18](#bib.bib18)].

Reproducible builds are thus the technical counterpart of the legal guarantee copyleft sought to provide. Where copyleft used the force of copyright to ensure that every binary was accompanied by its source, reproducible builds provide the cryptographic and procedural machinery to ensure that every binary is *derivable from* its source. Together, the two practices discharge the source–object equivalence on which the four freedoms depend.

For AI systems, the question becomes: can a training pipeline, analogous to a compiler, be made reproducible? The honest answer is that full reproducibility of contemporary deep learning is difficult but not impossible, and that the technical obstacles are increasingly well understood.




Q: What is the concept of "Reproducible Builds as a New Copyleft" in the context of free software community?
Q: How does the principle of reproducible builds ensure the generation of identical binaries?
Q: Which projects, such as Debian and Tails, are committed to the practice of reproducible builds?



Summary: This section explores the concept of "Reproducible Builds as a New Copyleft," emphasizing the importance of ensuring that any individual with the same declared source and toolchain can produce an identical binary, a principle deeply rooted in the free software community.

Keywords: Reproducible Builds, Copyleft, Free Software, Debian, Tails, Identical Binary, Source, Toolchain, Commitment, Methodology.

### 6.1 Sources of Non-Determinism in ML Training

In this section, we delve into the sources of non-determinism that can arise during the training phase of machine learning models. This discussion is part of a broader exploration of reproducibility challenges in ML, following the taxonomy proposed by Chen et al. [[5](#bib.bib5)]. The section begins by summarizing the key categories of reproducibility barriers identified by Chen et al., namely software randomness and hardware non-determinism. It then proceeds to elaborate on specific instances of these barriers, such as PRNG seeds, data-loader shuffling, dropout masks, and cuDNN algorithm selection. The aim is to provide a comprehensive understanding of the factors that can introduce variability in ML training, thereby impacting the reproducibility of results.


Chen et al. [[5](#bib.bib5)] offered a systematic taxonomy of reproducibility barriers for deep learning, dividing them into software randomness (PRNG seeds, data-loader shuffling, dropout masks) and hardware non-determinism (cuDNN algorithm selection, floating-point reduction order on GPUs). Their record-and-replay plus profile-and-patch framework was able to reproduce six open-source and one commercial deep-learning model exactly. Semmelrock et al.’s 2025 survey [[32](#bib.bib32)] expanded this analysis into a barriers-and-drivers matrix, identifying technology-driven, procedural, and educational levers and noting that reproducibility of large language models is particularly constrained by the sheer cost of retraining.

The U.S. Software Engineering Institute has argued that the non-determinism of ML is frequently overstated: with careful seed control and suppression of internal concurrency, “the myth” of ML irreproducibility collapses into a set of well-characterized engineering problems [[22](#bib.bib22)]. This is broadly consistent with the PyTorch project’s own reproducibility guidance [[29](#bib.bib29)]: with appropriate seed management and deterministic backend settings, training can be made repeatable on a given platform and release, though bit-exact reproducibility is generally not guaranteed across CPU/GPU boundaries, across GPU microarchitectures, or across framework versions.




Q: What are the key categories of reproducibility barriers in ML training, as identified by Chen et al.?
Q: How does software randomness contribute to non-determinism in ML training?
Q: What specific instances of hardware non-determinism are discussed in this section?



Summary: This section examines the sources of non-determinism in machine learning (ML) training, focusing on software randomness and hardware non-determinism, as outlined by Chen et al. [[5](#bib.bib5)]. It delves into specific instances of these categories.

Keywords: machine learning, non-determinism, training phase, reproducibility challenges, software randomness, hardware non-determinism, Chen et al., reproducibility barriers.

### 6.2 Deterministic Inference

In this document, Section 6.2 delves into the topic of Deterministic Inference, a critical area of focus that complements the broader discussion on Large Language Model (LLM) training. This section is strategically placed after the exploration of training methodologies, providing a transition to the inference phase. It specifically addresses a significant revelation from Thinking Machines Lab's September 2025 blog post, which debunks the common misconception about the non-determinism of temperature-zero LLM inference. The section elucidates the true cause of this non-determinism, revealing it to be the batch-size dependence of reduction kernels, a factor often overlooked in the discourse on LLM behavior.


A recent and important development concerns inference rather than training. Thinking Machines Lab, in a widely discussed September 2025 blog post [[16](#bib.bib16)], showed that the apparent non-determinism of temperature-zero LLM inference is not primarily due to floating-point non-associativity combined with GPU scheduling, but to the *batch-size dependence* of reduction kernels: a given prompt can be dispatched under different dynamic batch sizes, and the internal reduction tree changes accordingly. The authors provide batch-invariant kernels for RMSNorm, matrix multiplication, and attention, and demonstrate bit-identical outputs across 1,000 repeated runs on Qwen3-8B, at approximately a 61.5% throughput cost in their baseline implementation. The SGLang team [[19](#bib.bib19)] subsequently integrated these kernels with CUDA graphs, reducing the overhead to approximately 34.35%. In collaboration with the slime project, they also extended the approach to fully reproducible reinforcement-learning training, closing the train–inference gap that had silently rendered on-policy RL off-policy. The LLM-42 project [[12](#bib.bib12)] takes a different route: arguing that batch-invariant computation is fundamentally over-constrained because it strips GPU kernels of batch-adaptive parallelism strategies, it instead proposes a *scheduling-based decode–verify–rollback* protocol inspired by speculative decoding, which enforces determinism selectively and incurs overhead roughly proportional to the fraction of traffic that actually requires it.

What these results demonstrate is that bit-exact reproducibility of large models is a *tractable engineering problem* rather than a fundamental limit. The question is which parts of the pipeline need to be made deterministic, and at what cost, to satisfy a given governance requirement. This is the question the next section formulates as a requirements specification.




Q: What is the focus of Section 6.2 in this document?
Q: How does Section 6.2 relate to the training methodologies discussed earlier?
Q: What significant revelation from Thinking Machines Lab's September 2025 blog post is addressed in Section 6.2?



Summary: Section 6.2 of the document discusses Deterministic Inference, a crucial aspect of Large Language Model (LLM) training, which contradicts the misconception of non-determinism in temperature-based sampling.

Keywords: Deterministic Inference, Large Language Model (LLM), training methodologies, inference phase, Thinking Machines Lab, non-determinism, temperature-based sampling.

## 7 Requirements for AGI-oriented Reproducible Builds

In this document, Section 7 delves into the specific requirements for achieving AGI-oriented Reproducible Builds (AGI-RB). This section is a crucial part of the discussion on data governance, building upon the principles outlined in [[15](#bib.bib15)] and the Asilomar AI Principles [[10](#bib.bib10)]. It addresses the unique reproducibility challenges posed by AGI systems capable of recursive self-improvement or self-replication, which are not typically encountered with contemporary foundation models. The section outlines seven requirements, categorized into three groups, to ensure the reproducibility of AGI systems.


An AGI, as defined for the purposes of data governance in [[15](#bib.bib15)] following Principle 22 of the Asilomar AI Principles [[10](#bib.bib10)], is an AI system capable of recursive self-improvement or self-replication. Such a system poses distinctive reproducibility challenges that go beyond those identified for contemporary foundation models. We define a set of requirements for what we call an *AGI-oriented reproducible build* (AGI-RB).

The seven requirements fall into three categories. R1–R5 are engineering requirements at varying levels of current maturity, applicable with increasing technical effort to existing and near-term systems. R6 is a *research target* rather than a deployable specification: it identifies the correct invariant that a share-alike obligation must enforce in the AGI context, even though no existing architecture demonstrably satisfies it. R7 is a *feasibility constraint* on the entire framework, governing the pace and scope at which the other requirements can realistically be imposed.




Q: What are the specific requirements for achieving AGI-oriented Reproducible Builds (AGI-RB)?
Q: How does Section 7 address the reproducibility challenges posed by AGI systems capable of recursive self-improvement or self-replication?
Q: In what ways does Section 7 build upon the principles outlined in [[15](#bib.bib15)] and the Asilomar AI Principles [[10](#bib.bib10)]?



Summary: Section 7 focuses on the essential requirements for creating AGI-oriented Reproducible Builds (AGI-RB), addressing the unique reproducibility challenges posed by AGI systems capable of recursive self-improvement or self-replication.

Keywords: AGI-oriented Reproducible Builds, reproducibility challenges, AGI systems, recursive self-improvement, self-replication, data governance, Asilomar AI Principles.

### 7.1 R1. Complete Input Enumeration

In the document, Section 7.1, titled "R1. Complete Input Enumeration," is a critical component that outlines the comprehensive requirements for specifying the inputs that dictate the behavior of an AGI-RB (Advanced General Intelligence - Reproducible Build). This section is situated within the broader context of ensuring transparency and reproducibility in AI systems. It details the necessity of providing machine-readable information about the exact training corpus, preprocessing and tokenization code with pinned dependency versions, hyperparameters, initial weights or seed, optimizer state at each checkpoint, and a hash-verifiable description of the toolchain and hardware configuration. This meticulous approach aims to facilitate the exact replication of the trained system, thereby promoting trust and reliability in AI technologies.


An AGI-RB must specify, in machine-readable form, the complete set of inputs whose combination determines the trained system. At a minimum this includes: the exact training corpus (not merely descriptive metadata); all preprocessing and tokenization code with pinned dependency versions; all hyperparameters; the initial weights or the seed used to generate them; the optimizer state at each checkpoint; and a hash-verifiable description of the toolchain and hardware configuration. OSAID’s “data information” category is insufficient at this level: a substantially equivalent dataset will not yield bit-identical weights.




Q: What is the purpose of Section 7.1 in the document?
Q: How does Section 7.1 contribute to ensuring transparency and reproducibility in AI systems?
Q: What specific aspects of input specification does Section 7.1 cover for an AGI-RB?



Summary: Section 7.1, "R1. Complete Input Enumeration," emphasizes the importance of detailing all inputs that influence an AGI-RB's behavior for transparency and reproducibility in AI systems.

Keywords: AGI-RB, transparency, reproducibility, inputs, training corpus, preprocessing, tokenization.

### 7.2 R2. Deterministic Training Pipeline

In the document, Section 7.2, titled "R2. Deterministic Training Pipeline," delves into the critical aspects of ensuring reproducibility in machine learning model training. This section follows the broader discussion on model reproducibility and reliability, as outlined in Section 7.1. It focuses on the configuration of the training pipeline to guarantee that the specified inputs consistently yield the expected outputs, either directly or through a known-equivalent transformation. The section explores various techniques to achieve this, such as setting fixed PRNG seeds, employing deterministic cuDNN modes, and utilizing batch-invariant reduction kernels. It also addresses the practical considerations when full determinism is not achievable due to scalability constraints, proposing the concept of a "reproducibility budget" to define the acceptable level of numerical discrepancy.


The training pipeline must be configured such that the declared inputs reproduce the declared outputs under bit-identity, either directly or after a known-equivalent transformation. Techniques include fixed PRNG seeds, deterministic cuDNN modes, batch-invariant reduction kernels [[16](#bib.bib16)], and suppression of dynamic batching in distributed training. Where full determinism is infeasible for scale reasons, the pipeline must specify a *reproducibility budget*: the admissible numerical tolerance and the statistical test used to certify it.




Q: What is the focus of Section 7.2 in the document?
Q: How does Section 7.2 contribute to ensuring reproducibility in machine learning model training?
Q: What does Section 7.2 discuss regarding the configuration of the training pipeline?



Summary: Section 7.2, "R2. Deterministic Training Pipeline," emphasizes the importance of creating a reproducible and consistent machine learning model training process by configuring the training pipeline to ensure that predefined inputs consistently produce the expected outputs, either directly or via a known-equivalent transformation.

Keywords: deterministic training pipeline, reproducibility, machine learning model training, consistent outputs, known-equivalent transformation, configuration, inputs, expected outputs.

### 7.3 R3. Verifiable Toolchain and Hardware Binding

In this section, the document delves into the critical aspect of ensuring reproducibility in AGI-RB (Artificial General Intelligence - Reproducible Build) systems. Specifically, it focuses on the necessity of a verifiable toolchain and hardware binding. This discussion is a continuation of the broader theme of reproducibility, following the exploration of various factors influencing numerical results in AGI-RB systems. The section underscores the importance of either committing to specific hardware configurations and transparently disclosing them, or incorporating hardware-abstraction layers into the distribution. These layers, akin to the practices established by the reproducible-builds community for ordinary software, aim to replace non-deterministic primitives, thereby enhancing the predictability and reproducibility of results.


Because GPU microcode, CUDA versions, and interconnect topologies affect numerical results, an AGI-RB must either bind to specific hardware configurations (and disclose them) or ship with hardware-abstraction layers—patched libraries replacing non-deterministic primitives—as part of the distribution [[5](#bib.bib5)]. The practice parallels the dpkg-buildflags and cross-compilation hygiene established by the reproducible-builds community for ordinary software [[30](#bib.bib30)].




Q: What is the focus of the section regarding ensuring reproducibility in AGI-RB systems?
Q: How does the document emphasize the importance of a verifiable toolchain and hardware binding in AGI-RB systems?
Q: What is the broader theme that this section continues from, in the context of reproducibility in AGI-RB systems?



Summary: This section emphasizes the significance of a verifiable toolchain and hardware binding in ensuring reproducibility within AGI-RB systems, building upon the previous discussion on factors affecting numerical results.

Keywords: Verifiable Toolchain, Hardware Binding, Reproducibility, AGI-RB Systems, Numerical Results, Commitment, Specific Hardware, Transparency, Consistency, Integrity.

### 7.4 R4. Third-Party Attestation Infrastructure

In this section, we delve into the concept of R4, or Third-Party Attestation Infrastructure, which is a crucial component in the broader context of AGI (Artificial General Intelligence) safety and transparency. This section is situated within the document's discussion on AGI governance and security measures, specifically under the subtopic of RAG (Retrieval-Augmented Generation) indexing. The section explores the necessity of independent verification for open-source AI systems, akin to the role of reproducible-builds testers in software development. It proposes the establishment of a third-party infrastructure, potentially operated by entities like Hugging Face, MLCommons, or a similar consortium, to retrain or re-infer claimed AI systems and publish cryptographic hashes of the results. This infrastructure aims to ensure the integrity and reproducibility of AI models, fostering trust and accountability in the AGI ecosystem.


Few end users will themselves retrain an AGI. As in software, where reproducible-builds testers such as reproducible.debian.net publish independent verification, AGI-RB requires a third-party attestation infrastructure. Hugging Face, MLCommons, or a consortium analogous to the Reproducible Builds project could operate public verification pipelines that retrain, or at minimum re-infer, claimed open source AI systems and publish cryptographic hashes of the results. Small language models, as noted in [[14](#bib.bib14)], are particularly amenable to this since the retraining cost falls within ordinary research budgets. Regulatory frameworks are moving in this direction: the EU AI Act’s provisions for open-source foundation models [[7](#bib.bib7)] already treat openness as an exemption criterion, and reproducibility is increasingly discussed as a natural operational test for that criterion [[24](#bib.bib24)].




Q: What is the concept of R4, or Third-Party Attestation Infrastructure, in the context of AGI safety and transparency?
Q: How does the Third-Party Attestation Infrastructure contribute to the governance and security measures of AGI systems?
Q: Why is independent verification of open-source AI systems necessary, as discussed in the context of R4?



Summary: This section discusses R4, or Third-Party Attestation Infrastructure, a vital element in ensuring AGI safety and transparency. It emphasizes the importance of independent verification for open-source AI systems, drawing parallels to the role of third-party audits in traditional software development.

Keywords: Third-Party Attestation Infrastructure, AGI safety, transparency, independent verification, open-source AI systems, RAG indexing, AGI governance, security measures.

### 7.5 R5. Self-Improvement Trajectory Logging

In this document, Section 7.5, titled "R5. Self-Improvement Trajectory Logging," delves into a unique aspect of AGI systems. This section is situated within the broader context of AGI requirements and standards, focusing on the necessity for a reproducible build of self-improving systems. It elucidates the importance of documenting and preserving the entire self-modification trajectory, encompassing every intermediate checkpoint, self-generated code modifications, and datasets curated or generated by the system itself. This meticulous logging is crucial for understanding and replicating the evolution of such systems.


This is the requirement distinctive to AGI. A system capable of recursive self-improvement modifies, at each iteration, both itself and the way in which it processes data [[37](#bib.bib37)]. A reproducible build of such a system must therefore include not only the initial training artifacts but the full trajectory of self-modification: every intermediate checkpoint, every modification to the training code generated by the system itself, and every dataset generated or curated by the system for its own use. In practice this implies an append-only, cryptographically signed log of self-modification events, analogous in spirit to Certificate Transparency logs in the TLS ecosystem.




Q: What is the focus of Section 7.5 in this document?
Q: Why is documenting and preserving the self-modification trajectory important in AGI systems?
Q: What elements does Section 7.5 emphasize should be included in the self-improvement trajectory logging?



Summary: Section 7.5, "R5. Self-Improvement Trajectory Logging," emphasizes the critical need for AGI systems to maintain a detailed, reproducible record of their self-improvement process, including all intermediate stages, code modifications, and datasets used.

Keywords: AGI systems, self-improvement, reproducible build, self-modification trajectory, intermediate checkpoints, code modifications, datasets, documentation, preservation.

### 7.6 R6. Recursive Verifiability (Research Target)

In the document, Section 7.6, titled "R6. Recursive Verifiability (Research Target)," delves into a critical aspect of AGI architecture design. This section follows the discussion on R5, focusing on the verification property. Here, we explore the stringent requirement that the verification property must be maintained even when the system undergoes self-improvement. This involves ensuring that any modifications to the training code, made by the system itself, do not compromise the reproducibility of outputs. The section underscores the complexity of this constraint, highlighting its role as a crucial safeguard in the AGI era, akin to the viral constraint in earlier AI development.


A stronger requirement follows from R5: the verification property must itself be preserved under self-improvement. If a system modifies its own training code, the modified training code must also produce reproducible outputs, and the modification must be auditable. This is a non-trivial constraint on AGI architecture design: it restricts the space of legitimate self-improvement operations to those that preserve the reproducibility invariant. It is, we suggest, the AGI-era analogue of the viral propagation that copyleft achieved through its share-alike clause. Instead of propagating a licensing term, the invariant propagates a technical property.

We acknowledge that R6 is an open research problem rather than a deployable engineering specification. Preserving a reproducibility invariant across arbitrary self-modifications touches on long-standing questions about inner alignment, tiling agents, and reflective stability [[38](#bib.bib38)], and it is not obvious that any AGI architecture proposed to date satisfies the property. Our claim is therefore the weaker one that R6 identifies the correct *target*: whatever substantive form share-alike takes in the AGI context, it must operate at the level of invariants on self-modification rather than at the level of license terms on static artifacts.




Q: What is the focus of Section 7.6 in the document?
Q: How does the verification property need to be maintained in a self-improving AGI system, according to the research target discussed in Section 7.6?
Q: What specific challenge does Section 7.6 address regarding the verification property in AGI architecture design?



Summary: Section 7.6, "R6. Recursive Verifiability (Research Target)," discusses the necessity of maintaining the verification property in AGI systems during self-improvement, ensuring that any self-made modifications to the training code do not undermine reproducibility.

Keywords: Recursive Verifiability, AGI Architecture, Self-Improvement, Verification Property, Reproducibility, Training Code, Research Target.

### 7.7 R7. Sustainable Economic and Computational Model

In this document, Section 7.7, titled "R7. Sustainable Economic and Computational Model", delves into the practical implications of implementing a regulatory framework for Artificial General Intelligence (AGI). This section follows a discussion on the challenges and limitations of current AGI models, and precedes a section on potential solutions. It specifically addresses the economic feasibility of copyleft-like requirements in AGI development. The section argues that imposing full reproducibility on large-scale models, given current compute prices, is unrealistic for most actors. Consequently, it proposes a phased approach starting with domain-restricted small models and leveraging techniques like batch-invariant kernels and selective-determinism to make AGI development more sustainable and computationally efficient.


Finally, any copyleft-like requirement that is economically infeasible will be ignored in practice. Demanding full reproducibility of a trillion-parameter frontier model is, at 2026 compute prices, not a meaningful obligation to impose on most actors. A realistic AGI-RB regime must therefore (i) begin with domain-restricted small models [[14](#bib.bib14)]; (ii) exploit batch-invariant kernels [[16](#bib.bib16), [19](#bib.bib19)] and selective-determinism techniques such as decode–verify–rollback [[12](#bib.bib12)] to contain the verification tax; and (iii) tolerate verifiable-by-sampling regimes in which third parties rebuild only subsets of the training trajectory.

A potential objection deserves acknowledgment: reproducibility requirements, like any compliance burden, could entrench large incumbents who can afford the necessary infrastructure, producing the opposite of the democratizing effect intended—a dynamic Widder, West, and Whittaker [[36](#bib.bib36)] document in the political economy of “open” AI. The response lies in R7 itself: calibrating requirements to model scale and domain, phasing obligations as tooling matures, and situating attestation in neutral consortium infrastructure imposes comparable relative burdens rather than absolute costs only incumbents can absorb. As with the GPL—whose obligations scaled with acts of distribution rather than organizational size—an analogous scaling principle should govern AGI-RB.




Q: What is the focus of Section 7.7 in this document?
Q: How does Section 7.7 address the practical implications of a regulatory framework for AGI?
Q: What economic aspects of AGI development are explored in Section 7.7?



Summary: Section 7.7, "R7. Sustainable Economic and Computational Model", explores the economic and computational sustainability of a regulatory framework for Artificial General Intelligence (AGI), focusing on the feasibility of copyleft-like requirements in AGI development.

Keywords: Artificial General Intelligence (AGI), regulatory framework, economic feasibility, copyleft-like requirements, computational sustainability, AGI development.

## 8 MCP and the Dynamic Linking Layer: A Different Governance Problem

In this section, we delve into a distinct aspect of AI governance: the role of the Model Card and Provenance (MCP) framework within the Dynamic Linking Layer. This discussion diverges from our previous exploration of AI production, focusing instead on the runtime interactions of AI systems. We examine how MCP, alongside other runtime coupling standards like OpenAI's function-calling interface and Google's Agent-to-Agent protocol, shapes the governance of AI systems operating as nodes in a complex network of interconnected services. This analysis underscores the unique governance challenges posed by these runtime interactions and the importance of MCP in addressing them.


Our analysis so far has concerned the production of AI systems: the training pipeline, the weights, the self-improvement trajectory. But AI systems increasingly operate not in isolation but as nodes in a rapidly growing web of tool-using and tool-providing services. A class of runtime coupling standards has emerged to regulate these interactions: OpenAI’s function-calling interface [[23](#bib.bib23)], Google’s Agent-to-Agent (A2A) protocol [[13](#bib.bib13)], and various framework-level tool abstractions in libraries such as LangChain all share the same architectural role. For concreteness, we focus in what follows on Anthropic’s *Model Context Protocol* (MCP), introduced in late 2024 and now implemented across a broad range of AI products [[1](#bib.bib1)]; MCP standardizes how models discover and invoke external tools, resources, and prompts at runtime. A model with MCP access can read a user’s calendar, query a database, post to a repository, or call another model’s inference endpoint, all within the same conversational turn. Our argument is not specific to MCP, however: it applies *mutatis mutandis* to any standard that plays the same coupling role. Where we write “MCP” below, the reader may substitute any sufficiently general successor or competitor protocol.

MCP is not, in itself, a training-time artifact; it is a runtime coupling mechanism. In this respect it stands in the same relation to the AI system that *dynamic linking* stands to an executable in classical software. And this analogy is more than rhetorical: it has direct, and largely overlooked, implications for the governance framework developed in this paper.




Q: What is the focus of the discussion in this section regarding AI governance?
Q: How does the Model Card and Provenance (MCP) framework influence the governance of AI systems in the Dynamic Linking Layer?
Q: What other runtime coupling standards are mentioned alongside MCP in shaping AI system governance?



Summary: This section explores the governance of AI systems through the lens of the Model Card and Provenance (MCP) framework, focusing on runtime interactions and coupling standards like OpenAI's function-calling interface and Google's Agent-to-Agent protocol.

Keywords: Model Card and Provenance (MCP), runtime interactions, Dynamic Linking Layer, AI governance, OpenAI's function-calling interface, Google's Agent-to-Agent protocol, AI systems, nodes, coupling standards.

### 8.1 Why Copyleft Never Reached the Linking Layer

In this document, Section 8.1 delves into the complexities of copyleft licensing, specifically focusing on its application to the linking layer. This section is a critical analysis of the GNU project's history, highlighting the legal battles and philosophical debates surrounding the copyleft obligation. It explores the nuanced distinctions between derivative works, mere aggregations, static and dynamic linking, and invocation across process boundaries. The section underscores the pragmatic considerations that led to the creation of the Lesser General Public License (LGPL), as the Free Software Foundation (FSF) opted not to extend copyleft to infrastructural libraries.


The history of the GNU project is in part a history of litigated edge cases over where the copyleft obligation stops. The distinction between a derivative work and a mere aggregation, between static and dynamic linking, between invocation across a process boundary and invocation within it—these questions were never cleanly resolved. The LGPL exists precisely because the FSF decided, for pragmatic reasons, not to push copyleft across the linking boundary for libraries deemed infrastructural [[33](#bib.bib33)]. GPLv3 introduced carefully negotiated language around “System Libraries” and “Corresponding Source” to keep the viral effect within tractable limits [[8](#bib.bib8)].

The underlying difficulty is that dynamic linking dissolves the artifact that copyright law is designed to regulate. When program loads library at runtime, there is no distributed “work” that combines both; there are two works that interact in a user’s memory. Copyright’s grip weakens as we move from the static object file to the running process, and it disappears entirely when interaction takes place across a network boundary—the Affero clause of the GNU Affero General Public License (AGPLv3) being an elaborate attempt, widely regarded as partially successful at best, to plug that specific hole.

MCP makes this problem central rather than peripheral. A GPT-class model calling a third-party MCP server to retrieve a document is not distributing anything to anyone; it is performing a runtime interaction. If the model and the server are both “open source AI” in the OSAID sense, well and good; but nothing in the current OSAID, MOF, or OpenMDW frameworks says anything about the *edges* that connect them. The licensing regime is a set of rules for what each node must disclose about itself, and is silent on the protocols by which nodes interact.




Q: What are the legal battles and philosophical debates surrounding the copyleft obligation as discussed in Section 8.1?
Q: How does Section 8.1 analyze the nuanced distinctions between derivative works, mere aggregations, static and dynamic linking, and invocation across process boundaries in the context of copyleft?
Q: What are the reasons why copyleft never reached the linking layer, as explored in Section 8.1?



Summary: Section 8.1 examines the reasons why copyleft licensing, as advocated by the GNU project, has not been effectively applied to the linking layer, delving into the legal and philosophical complexities, including the distinctions between derivative works, linking methods, and process invocation.

Keywords: copyleft licensing, GNU project, legal battles, philosophical debates, derivative works, linking layer, static linking, dynamic linking, process boundaries.

### 8.2 The Masnick Insight: Protocols, Not Platforms

In this section, we delve into the implications of Masnick's argument on social media content moderation, as presented in Section 8.2 titled "The Masnick Insight: Protocols, Not Platforms". This part of the document builds upon Masnick's critique of the platform era, focusing on the bundling of functions such as hosting, routing, and user interface within a single corporate entity. By examining these functions, we aim to understand how decentralization could potentially mitigate the pathologies associated with centralized platforms, as suggested by Masnick.


Masnick [[21](#bib.bib21)], writing about social media content moderation, argued that many of the pathologies of the platform era derive from the bundling, within a single corporate gatekeeper, of functions that the open-protocol era kept architecturally separate. Extending Masnick’s argument, we can identify three such functions in particular: hosting, routing, and user interface. Centralized platforms bundle these into a single governance surface, which is why Facebook’s content-moderation decisions attract the attention they do: the platform is simultaneously the host, the router, and the primary interface. A protocol-based architecture, Masnick argues, would push moderation decisions to the edges—to interfaces, clients, filters—while keeping the protocol itself neutral and open. The historical precedent is email: SMTP as a protocol remains universal, while thousands of clients, servers, and filtering services compete on the user-facing experience.

The parallel to the AI tool-use layer is striking. MCP, if it succeeds, will be to AI assistants roughly what SMTP is to email: a lingua franca that decouples the production of capabilities from the consumption of capabilities. A well-governed MCP ecosystem would then exhibit many of the properties Masnick attributes to protocol-based social media: competition at the client (assistant) layer, innovation at the tool-provider layer, and governance distributed across edges rather than concentrated in a single gatekeeper. Conversely, a poorly governed MCP ecosystem—one in which a single vendor controls the registry, the reference implementations, and the authentication infrastructure—would exhibit exactly the platform pathologies that Masnick diagnoses for current social media.

The analogy has limits. Masnick’s concern was end-user speech and content-moderation pluralism, whereas the governance problem at the AI tool-use layer centers on tool-provider competition, portability of user tool ecosystems, and avoidance of vendor lock-in at the orchestration layer. These are different first-order concerns, and the Masnick framework cannot simply be imported wholesale. What does transfer, however, is the structural insight that separating the three bundled functions—hosting, routing, and interface—produces governance properties that no centralized platform design can match. It is this structural claim, not the content-moderation application, that we apply to MCP.

This suggests that the governance of the AI linking layer is a fundamentally different problem from the governance of the training layer, and requires different tools. Copyleft and reproducible builds are appropriate for the production side, where the question is how a system comes into being. Protocol governance in the Masnick sense is appropriate for the linking side, where the question is how systems interact. Conflating the two, or attempting to extend a licensing framework designed for one into the other, is likely to produce the same unsatisfying results that extending copyright law to cover dynamic linking produced in the 1990s.




Q: What is the main argument presented by Masnick in "The Masnick Insight: Protocols, Not Platforms"?
Q: How does Masnick's critique of the platform era relate to social media content moderation?
Q: What role do protocols play in Masnick's vision for decentralization and mitigating pathologies in social media?



Summary: This section explores Mike Masnick's argument that decentralization through protocols rather than centralized platforms could address issues in social media content moderation, as discussed in "The Masnick Insight: Protocols, Not Platforms".

Keywords: Mike Masnick, decentralization, protocols, platform era, content moderation, hosting, routing, user interface, corporate entity, pathologies.

### 8.3 Requirements for MCP-Layer Governance

In this document, Section 8.3 delves into the essential requirements for MCP-Layer Governance. Following a comprehensive discussion on the MCP protocol's architecture and functionality, this section focuses on the governance aspects that ensure its effective and fair operation. It outlines the necessary conditions for a robust MCP-style protocol, emphasizing the importance of open standards, non-proprietary authentication, and user portability. This context provides a bridge between the technical implementation and the broader implications of MCP-Layer Governance.


A full development of this point would require another paper, but we can indicate the direction. An MCP-style protocol designed for good governance would need, at minimum: (i) an open, standards-body-maintained specification that no single vendor can unilaterally alter—exactly the property Masnick identifies as the core of the protocol/platform distinction; (ii) portable, non-proprietary authentication so that a user or organization can switch between clients without losing access to their tool ecosystem—the email analogue being the portability of one’s address book across providers; (iii) transparent logging of tool invocations in a form the user controls, so that audit of AI behavior is possible without depending on the goodwill of any single vendor; and (iv) explicit, machine-readable licensing and provenance metadata on tools themselves, so that the copyleft status of downstream artifacts produced by tool composition can be determined rather than assumed.

The last of these is particularly important in light of the rewrite problem discussed in Section [5](#S5). If an AI system with tool access can generate a new artifact by composing outputs from multiple MCP-accessed sources, the licensing status of the result is an open question that current MCP implementations do not attempt to answer. Metadata requirements at the protocol level would begin to address this, not by re-imposing copyleft viral propagation (which would be both technically unenforceable and contrary to the Masnick protocol-neutrality principle), but by enabling downstream reasoning about provenance.

We note, finally, that MCP-like protocols exhibit the same structural vulnerability to incumbent capture that Masnick identifies for social-media platforms. MCP is currently maintained by Anthropic, a single commercial entity; long-term governance of the specification is unsettled. If MCP becomes the AI industry’s SMTP, its stewardship should reside in a neutral body along the lines of the IETF, not in any single laboratory. This is an institutional design question likely to prove as consequential as the OSAID debate, if not more so.




Q: What are the essential requirements for MCP-Layer Governance as discussed in Section 8.3?
Q: How does Section 8.3 emphasize the importance of open standards, non-proprietary authentication, and user portability in MCP-Layer Governance?
Q: What conditions are outlined in Section 8.3 for a robust MCP-style protocol?



Summary: Section 8.3 of this document discusses the critical requirements for MCP-Layer Governance, emphasizing the need for open standards, non-proprietary authentication, and user portability to ensure the effective and fair operation of the MCP protocol.

Keywords: MCP-Layer Governance, open standards, non-proprietary authentication, user portability, MCP protocol, effective operation, fair operation.

## 9 Connection to AGI Data Governance

In this document, Section 9 delves into the intricate relationship between AGI (Artificial General Intelligence) and data governance. It builds upon the foundational work presented in [[15](#bib.bib15)], where seven unique data-governance challenges associated with AGI were meticulously outlined. This section, therefore, serves as an extension, focusing on how the AGI-RB framework effectively tackles several of these challenges, particularly R5 and R6, which establish crucial technical prerequisites for data provenance tracking under recursive self-improvement.


In [[15](#bib.bib15)] we identified seven data-governance challenges specific to AGI: unpredictability of data collection, divergent optimization criteria, AGI-to-AGI data sharing, provenance tracking under recursive self-improvement, intellectual-property complications, cross-border fragmentation, and temporal mismatch between governance frameworks and system evolution. The AGI-RB framework addresses several directly. Most importantly, R5 and R6 together impose technical preconditions on provenance tracking under recursive self-improvement: a self-modifying system whose modifications preserve reproducibility is amenable to after-the-fact audit in a way that a black-box system is not. R4 offers a partial answer to the temporal challenge, since governance can rely on continuously updated verification infrastructure rather than ex ante certification that inevitably goes stale.

The intellectual-property challenge intersects with the OSAID data compromise in a way that deserves closer attention than we can give here. If an AGI generates new training data for self-improvement, a reproducibility requirement implies that those generated datasets must be disclosable, raising the question of ownership [[31](#bib.bib31)]. Our tentative view, consistent with [[14](#bib.bib14)], is that a copyleft-like obligation attached to AGI-generated artifacts—requiring release under terms compatible with further reproducibility—may be the cleanest resolution: a genuine share-alike obligation whose content is reproducibility rather than source availability. More concretely, AGI systems deployed in domains of public interest—government procurement, defense, safety-critical medicine—should be required to satisfy at least R1–R4, with R5–R6 phased in as technical capability matures, structurally analogous to what the GPL achieved for federally funded software but implemented through reproducibility rather than licensing alone.




Q: How does the AGI-RB framework address the data governance challenges outlined in [[15](#bib.bib15)]?
Q: Which specific data governance challenges (R5 and R6) does Section 9 focus on in relation to the AGI-RB framework?
Q: What are the technical prerequisites established by R5 and R6 in the context of AGI data governance?



Summary: Section 9 explores the connection between AGI (Artificial General Intelligence) and data governance, expanding on the seven data-governance challenges for AGI introduced in [[15](#bib.bib15)]. It highlights how the AGI-RB framework addresses challenges R5 and R6, focusing on technical prerequisites.

Keywords: AGI, Artificial General Intelligence, data governance, data-governance challenges, AGI-RB framework, technical prerequisites, R5, R6.

## 10 Conclusion

In the concluding section of this document, titled "10 Conclusion", we summarize the key points discussed. The section delves into the limitations of applying the copyleft concept, traditionally used in software freedom, to modern AI systems and the prospect of AGI. It argues that the deterministic relationship between source and object code, which made copyleft effective in software, does not hold true for AI. The section further critiques the notion that advanced AI assistants alone can solve the problem, emphasizing the need for a new approach to address the unique challenges posed by AI.


Copyleft was a legal hack that worked because a technical fact—the deterministic relationship between source and object code—made the legal obligation substantively meaningful. That fact no longer holds for modern AI systems, and will hold even less for AGI. Maffulli is right that the software-freedom tradition cannot simply be rewritten in AI terms using the old legal toolkit, but wrong to suggest that the solution is already arriving in the form of more powerful AI assistants. What is needed is a technical reconstruction of the source–object equivalence, adapted to systems whose behavior emerges from code, data, weights, seeds, toolchains, hardware, and increasingly from their own prior self-modifications.

Reproducible builds, extended from the software context to the full training and inference pipeline, are the natural candidate. We have formulated seven requirements for AGI-oriented reproducible builds—five engineering requirements at varying maturity levels, one research target (R6), and one feasibility constraint (R7)—connected them to ongoing international work, and situated them within the broader landscape of AGI data governance. Two further phenomena—AI-assisted rewriting of licensed code and the rise of MCP-style dynamic coupling—extend the diagnosis: for the former, reproducibility provides the only remaining point of purchase once cost asymmetry erodes; for the latter, Masnick’s protocol-governance template offers a structural alternative to platform pathologies. The framework is preliminary, and much remains to be worked out, but the direction is correct.

The first liberation, to borrow Maffulli’s phrase, gave us the code. The second liberation, if it is to mean anything more than a new dependency on opaque AI services, must give us the code *and* the verifiable procedure by which the code became what it is. For AGI, anything less is not freedom but faith.




1. Q: What are the limitations of applying the copyleft concept to modern AI systems and AGI?
2. Q: How does the deterministic relationship between source and object code impact the effectiveness of copyleft in AI systems?
3. Q: What critique is made regarding the role of advanced AI assistants in solving complex problems?



Summary: The concluding section, "10 Conclusion", summarizes the limitations of applying copyleft principles to AI systems and AGI, emphasizing the lack of a deterministic relationship between source and object code in AI, unlike in software. It also critiques the idea that advanced AI assistants can solely solve the challenges of AI governance and ethics.

Keywords: copyleft, AI systems, AGI, deterministic relationship, source code, object code, AI governance, ethics, advanced AI assistants.

#### Acknowledgements.

In the concluding part of our research paper, we dedicate a section to express our gratitude and acknowledge the contributions that have facilitated our study. This section, titled "Acknowledgements," provides a platform to recognize the financial support we received. Specifically, we highlight the JSPS KAKENHI Grant Number 26K15531, which played a crucial role in funding our project.


This work was supported by JSPS KAKENHI Grant Number 26K15531.




Q: Who provided financial support for the research project?
Q: What is the specific grant number that funded the project?
Q: How did the JSPS KAKENHI Grant Number 26K15531 contribute to the research?



Summary: The "Acknowledgements" section of the research paper expresses gratitude for financial support received, particularly from the JSPS KAKENHI Grant Number 26K15531.

Keywords: Acknowledgements, financial support, JSPS KAKENHI, Grant Number 26K15531, research project funding.

#### Disclosure of Interests.

In the methodology section of this research paper, we delve into the transparency and integrity of our work. Here, we explicitly disclose any potential conflicts of interest that could influence the findings or conclusions. This subsection, titled "Disclosure of Interests," outlines the author's affiliations and participations, ensuring the reader of our commitment to unbiased research. It is crucial to note that the author, while an active member of the Open Source Initiative community and a participant in OSAID discussions, asserts no competing interests relevant to the content of this paper.


The author has no competing interests to declare that are relevant to the content of this paper. The author is a member of the Open Source Initiative community and has participated in OSAID discussions.




Q: What is the purpose of the "Disclosure of Interests" subsection in the methodology section of this research paper?
Q: How does the author ensure transparency and integrity in this research paper regarding potential conflicts of interest?
Q: What affiliations and participations of the author are disclosed in the "Disclosure of Interests" subsection?



Summary: The "Disclosure of Interests" section in the methodology of this research paper outlines the author's affiliations and participations to ensure transparency and integrity, preventing potential conflicts of interest that could bias the findings or conclusions.

Keywords: Disclosure, Interests, Transparency, Integrity, Conflicts of Interest, Author Affiliations, Open Source Initiative, Unbiased Research.

## References

In this document, the "References" section is dedicated to citing the sources of information and ideas presented throughout the content. This section, located towards the end of the document, provides a comprehensive list of references, including [1] "Anthropic: Introducing the Model Context Protocol" (2024) and [2] "Open Source Artificial Intelligence Definition 1.0 – A 'Take It or Leave It' Approach for Open Source AI Systems?" (2025) by Benhamou and Reymond. These references serve to acknowledge the original authors and publications, allowing readers to explore the sources in more detail and verify the information provided.


- [1]
Anthropic: Introducing the Model Context Protocol (2024).
[https://www.anthropic.com/news/model-context-protocol](https://www.anthropic.com/news/model-context-protocol)
- [2]
Benhamou, Y., Reymond, M.: Open Source Artificial Intelligence Definition 1.0 – A “Take It or Leave It” Approach for Open Source AI Systems? Kluwer Copyright Blog, March 4 (2025). [https://legalblogs.wolterskluwer.com/copyright-blog/open-source-artificial-intelligence-definition-10-a-take-it-or-leave-it-approach-for-open-source-ai-systems/](https://legalblogs.wolterskluwer.com/copyright-blog/open-source-artificial-intelligence-definition-10-a-take-it-or-leave-it-approach-for-open-source-ai-systems/)
- [3]
Carlini, N., Tramèr, F., Wallace, E., Jagielski, M., Herbert-Voss, A., Lee, K., Roberts, A., Brown, T., Song, D., Erlingsson, U., Oprea, A., Raffel, C.: Extracting Training Data from Large Language Models. In: 30th USENIX Security Symposium, pp. 2633–2650 (2021). [https://www.usenix.org/conference/usenixsecurity21/presentation/carlini-extracting](https://www.usenix.org/conference/usenixsecurity21/presentation/carlini-extracting)
- [4]
Carlini, N., Jagielski, M., Choquette-Choo, C. A., Paleka, D., Pearce, W., Anderson, H., Terzis, A., Thomas, K., Tramèr, F.: Poisoning Web-Scale Training Datasets is Practical. arXiv:2302.10149 (2023). [https://doi.org/10.48550/arXiv.2302.10149](https://doi.org/10.48550/arXiv.2302.10149)
- [5]
Chen, B., Wen, M., Shi, Y., Lin, D., Rajbahadur, G. K., Jiang, Z. M.: Towards Training Reproducible Deep Learning Models. In: Proceedings of the 44th International Conference on Software Engineering (ICSE ’22), pp. 2202–2214 (2022). [https://doi.org/10.1145/3510003.3510163](https://doi.org/10.1145/3510003.3510163)
- [6]
Claburn, T.: Chardet Dispute Shows How AI Will Kill Software Licensing,
Argues Bruce Perens. The Register, March 6 (2026).
[https://www.theregister.com/2026/03/06/ai_kills_software_licensing/](https://www.theregister.com/2026/03/06/ai_kills_software_licensing/)
- [7] European Parliament and Council: Regulation (EU) 2024/1689 of 13 June 2024 Laying Down Harmonized Rules on Artificial Intelligence (AI Act). Official Journal of the European Union (2024)
- [8]
Free Software Foundation: GNU General Public License, Version 3 (2007). [https://www.gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html)
- [9]
Free Software Foundation: What Is Free Software? (2024). [https://www.gnu.org/philosophy/free-sw.html](https://www.gnu.org/philosophy/free-sw.html)
- [10]
Future of Life Institute: Asilomar AI Principles (2017).
[https://futureoflife.org/2017/08/11/ai-principles/](https://futureoflife.org/2017/08/11/ai-principles/)
- [11]
Generative AI Commons: Model Openness Tool (2025). [https://isitopen.ai/](https://isitopen.ai/)
- [12]
Gond, R., Kamath, A. K., Ramjee, R., Panwar, A.: LLM-42: Enabling Determinism in LLM Inference with Verified Speculation. arXiv:2601.17768 (2026). [https://doi.org/10.48550/arXiv.2601.17768](https://doi.org/10.48550/arXiv.2601.17768)
- [13]
Google: Announcing the Agent2Agent Protocol (A2A). Google Developers Blog (2025). [https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [14]
Hatta, M.: “Copyleft” in the Context of GenAI. Hack or Be Hacked (Substack), October 21 (2024). [https://mhatta.substack.com/p/copyleft-in-the-context-of-genai](https://mhatta.substack.com/p/copyleft-in-the-context-of-genai)
- [15]
Hatta, M.: Several Issues Regarding Data Governance in AGI. In: Iklé, M., Kolonin, A., Bennett, M. (eds.) Artificial General Intelligence. AGI 2025. Lecture Notes in Computer Science, vol. 16057, pp. 239–249. Springer, Cham (2026). [https://doi.org/10.1007/978-3-032-00686-8_22](https://doi.org/10.1007/978-3-032-00686-8_22)
- [16]
He, H., Thinking Machines Lab: Defeating Nondeterminism in LLM Inference. Thinking Machines Lab: Connectionism, September (2025). [https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)
- [17]
Kuhn, B. M.: Open Source AI Definition Erodes the Meaning of “Open Source”. Software Freedom Conservancy Blog, October 31 (2024). [https://sfconservancy.org/blog/2024/oct/31/open-source-ai-definition-osaid-erodes-foss/](https://sfconservancy.org/blog/2024/oct/31/open-source-ai-definition-osaid-erodes-foss/)
- [18]
Lamb, C., Zacchiroli, S.: Reproducible Builds: Increasing the Integrity of Software Supply Chains. IEEE Software 39(2), 62–70 (2022). [https://doi.org/10.1109/MS.2021.3073045](https://doi.org/10.1109/MS.2021.3073045) . IEEE Software Best Paper Award 2022
- [19]
LMSYS: Towards Deterministic Inference in SGLang and Reproducible RL Training. LMSYS Blog, September 22 (2025). [https://www.lmsys.org/blog/2025-09-22-sglang-deterministic/](https://www.lmsys.org/blog/2025-09-22-sglang-deterministic/)
- [20]
Maffulli, S.: The Second Liberation: AI Is the Final Frontier of Copyleft. Personal blog, March 16 (2026). [https://www.maffulli.net/2026/03/16/ai-final-frontier-of-copyleft/](https://www.maffulli.net/2026/03/16/ai-final-frontier-of-copyleft/)
- [21]
Masnick, M.: Protocols, Not Platforms: A Technological Approach to Free Speech. Knight First Amendment Institute, Columbia University, 19–05 (2019). [https://knightcolumbia.org/content/protocols-not-platforms-a-technological-approach-to-free-speech](https://knightcolumbia.org/content/protocols-not-platforms-a-technological-approach-to-free-speech)
- [22]
Mellinger, A., Justice, D., Connor, M., Gallagher, S., Brooks, T.: The Myth of Machine Learning Non-Reproducibility and Randomness for Acquisitions and Testing, Evaluation, Verification, and Validation. Software Engineering Institute, Carnegie Mellon University, Insights Blog, January 13 (2025). [https://doi.org/10.58012/g17y-gp09](https://doi.org/10.58012/g17y-gp09)
- [23]
OpenAI: Function Calling and Other API Updates. OpenAI Blog, June 13 (2023). [https://openai.com/blog/function-calling-and-other-api-updates](https://openai.com/blog/function-calling-and-other-api-updates)
- [24]
Open Future: The AI Act and Open Source AI. Open Future Observatory (2024). [https://openfuture.eu/observatory/aia-open-source/](https://openfuture.eu/observatory/aia-open-source/)
- [25]
Open Source Initiative: The Open Source AI Definition v1.0 (2024). [https://opensource.org/ai/open-source-ai-definition](https://opensource.org/ai/open-source-ai-definition)
- [26]
Open Source Initiative: Deep Dive: Data Governance (Online Event, October 1–3, 2025). [https://opensource.org/events/deep-dive-data-governance](https://opensource.org/events/deep-dive-data-governance)
- [27]
Open Source Initiative: OSAID FAQs (2025). [https://opensource.org/ai/faq](https://opensource.org/ai/faq)
- [28]
Open Source Initiative: Report from OSS EU 2025 and AI_dev: What’s Next for OSAID (2025). [https://opensource.org/blog/report-from-oss-eu-2025-and-ai_dev-whats-next-for-osaid](https://opensource.org/blog/report-from-oss-eu-2025-and-ai_dev-whats-next-for-osaid)
- [29]
The PyTorch Project: Reproducibility — PyTorch Documentation (2024). [https://docs.pytorch.org/docs/stable/notes/randomness.html](https://docs.pytorch.org/docs/stable/notes/randomness.html)
- [30]
The Reproducible Builds Project: Reproducible Builds—A Set of Software Development Practices That Create an Independently-Verifiable Path from Source to Binary Code. [https://reproducible-builds.org/](https://reproducible-builds.org/) (2024)
- [31]
Samuelson, P.: Generative AI Meets Copyright. Science 381(6654), 158–161 (2023). [https://doi.org/10.1126/science.adi0656](https://doi.org/10.1126/science.adi0656)
- [32]
Semmelrock, H., Ross-Hellauer, T., Kopeinik, S., Theiler, D., Haberl, A., Thalmann, S., Kowald, D.: Reproducibility in Machine-Learning-Based Research: Overview, Barriers, and Drivers. AI Magazine 46(2), e70002 (2025). [https://doi.org/10.1002/aaai.70002](https://doi.org/10.1002/aaai.70002)
- [33]
Stallman, R. M.: Free Software, Free Society: Selected Essays of Richard M. Stallman. GNU Press, Boston (2002). [https://www.gnu.org/philosophy/fsfs/rms-essays.pdf](https://www.gnu.org/philosophy/fsfs/rms-essays.pdf)
- [34]
White, M., Haddad, I., Osborne, C., Liu, X.-Y. (Yanglet), Abdelmonsef, A., Varghese, S., Le Hors, A.: The Model Openness Framework: Promoting Completeness and Openness for Reproducibility, Transparency, and Usability in Artificial Intelligence. arXiv:2403.13784 (2024). [https://doi.org/10.48550/arXiv.2403.13784](https://doi.org/10.48550/arXiv.2403.13784)
- [35]
White, M.: The Open Source Legacy and AI’s Licensing Challenge. Linux Foundation Blog, May 22 (2025). [https://www.linuxfoundation.org/blog/the-open-source-legacy-and-ais-licensing-challenge](https://www.linuxfoundation.org/blog/the-open-source-legacy-and-ais-licensing-challenge)
- [36]
Widder, D. G., West, S., Whittaker, M.: Open (for Business): Big Tech, Concentrated Power, and the Political Economy of Open AI. SSRN preprint (2023). [https://doi.org/10.2139/ssrn.4543807](https://doi.org/10.2139/ssrn.4543807)
- [37]
Yampolskiy, R. V.: Artificial Superintelligence: A Futuristic Approach. Chapman and Hall/CRC (2015). [https://doi.org/10.1201/b18612](https://doi.org/10.1201/b18612)
- [38]
Yudkowsky, E., Herreshoff, M.: Tiling Agents for Self-Modifying AI, and the Löbian Obstacle. Machine Intelligence Research Institute Technical Report (2013). [https://intelligence.org/files/TilingAgents.pdf](https://intelligence.org/files/TilingAgents.pdf)

1. Q: What sources of information and ideas are cited in this document's "References" section?
2. Q: Which publication by Benhamou and Reymond is included in the references of this document?
3. Q: What is the purpose of the "References" section in this document?


Summary: The "References" section of this document lists sources of information and ideas, including "Anthropic: Introducing the Model Context Protocol" (2024) and "Open Source Artificial Intelligence Definition 1.0 – A 'Take It or Leave It' Approach for Open Source AI Systems?" (2025) by Benhamou and Reymond.

Keywords: References, sources, information, ideas, Anthropic, Model Context Protocol, Benhamou, Reymond, Open Source AI, 2024, 2025.
