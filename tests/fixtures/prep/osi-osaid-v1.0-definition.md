#### version 1.0

This section, titled "version 1.0," is a crucial part of the Open Source AI Documentation. It provides essential links to related resources, enhancing the user's understanding and engagement with the document. These resources include Frequently Asked Questions (FAQs), a list of endorsements, a comprehensive checklist, and an option to endorse the OSAID. By clicking on these links, users can access additional information, testimonials, and guidelines, thereby enriching their experience with the document.


[See FAQs](https://opensource.org/ai/faq)[See list of endorsements](https://opensource.org/ai/endorsements)[See Checklist](https://opensource.org/ai/checklist)[Endorse the OSAID](#endorse)




Q: What version of the Open Source AI Documentation is this section for?
Q: What resources are provided in this "version 1.0" section of the Open Source AI Documentation?
Q: How can users access additional information and guidelines related to the Open Source AI Documentation?



Summary: The "version 1.0" section of the Open Source AI Documentation offers valuable links to related resources, such as FAQs, endorsements, a checklist, and an endorsement option, to deepen users' understanding and engagement with the document.

Keywords: Open Source AI Documentation, version 1.0, FAQs, endorsements, checklist, endorsement option, user engagement, resource links.

## Preamble




### Why we need Open Source Artificial Intelligence (AI)

In this document, the section "Why we need Open Source Artificial Intelligence (AI)" is a critical component that follows an introduction to the potential of AI and its current state. This section delves into the rationale behind advocating for Open Source principles in the realm of AI. It underscores the historical success of Open Source in fostering innovation, collaboration, and widespread benefits through the removal of barriers to software usage and improvement. The section then draws a parallel between the advantages of Open Source software and the necessity for similar freedoms in AI, emphasizing the importance of autonomy, transparency, and collaborative improvement for AI developers, deployers, and end-users.


Open Source has demonstrated that massive benefits accrue to everyone after removing the barriers to learning, using, sharing and improving software systems. These benefits are the result of using licenses that adhere to the Open Source Definition. For AI, society needs at least the same essential freedoms of Open Source to enable AI developers, deployers and end users to enjoy those same benefits: autonomy, transparency, frictionless reuse and collaborative improvement.




Q: What is the significance of Open Source principles in the context of AI?
Q: How has Open Source contributed to innovation and collaboration in software development?
Q: What are the potential benefits of applying Open Source principles to AI?



Summary: The section "Why we need Open Source Artificial Intelligence (AI)" emphasizes the importance of adopting Open Source principles in AI development, highlighting its historical success in promoting innovation, collaboration, and widespread benefits by eliminating barriers to software usage and improvement.

Keywords: Open Source, Artificial Intelligence, innovation, collaboration, widespread benefits, software usage, improvement, historical success, barriers removal.

## 

When we refer to a “system,” we are speaking both broadly about a fully functional structure and its discrete structural elements. To be considered Open Source, the requirements are the same, whether applied to a **system**, a **model**, **weights and parameters**, or other structural elements.

In this section, we delve into the concept of Open Source AI, a topic that complements our broader discussion on AI ethics and governance. Here, we clarify the definition of a "system" in the context of Open Source AI, encompassing both the holistic structure and its individual components. This explanation sets the stage for understanding the four essential freedoms associated with Open Source AI: the ability to use, study, modify, and share the system, model, weights, parameters, or other structural elements without restriction. This section is pivotal in establishing the principles that guide the responsible development and deployment of AI technologies.


An *Open Source AI* is an AI system made available under terms and in a way that grant the freedoms[1](#398e6e4c-5d98-4796-8bda-5bf97dc04a76) to:

- **Use** the system for any purpose and without having to ask for permission.
- **Study** how the system works and inspect its components.
- **Modify** the system for any purpose, including to change its output.
- **Share** the system for others to use with or without modifications, for any purpose.

These freedoms apply both to a fully functional system and to discrete elements of a system. A precondition to exercising these freedoms is to have access to the preferred form to make modifications to the system.




Q: What does the term "system" encompass in the context of Open Source AI?
Q: How do the requirements for Open Source AI apply to different structural elements, such as models, weights, and parameters?
Q: What are the four essential freedoms associated with Open Source AI?



Summary: This section explains the concept of Open Source AI, defining a "system" as both a fully functional structure and its individual components, with the same requirements applying to models, weights, parameters, or other elements.

Keywords: Open Source AI, system, model, weights, parameters, freedoms, use, study, modify, share.

### Preferred form to make modifications to machine-learning systems

In the document's advanced technical section, we delve into the intricacies of modifying machine-learning systems. This part, titled "Preferred form to make modifications to machine-learning systems," outlines the essential components required for any alterations. It emphasizes the importance of comprehensive data information, which must be accessible under OSI-approved terms. This includes a detailed description of all data used for training, encompassing even unshareable data, to enable a skilled professional to construct a substantially equivalent system.


The preferred form of making modifications to a machine-learning system must include all the elements below:

- **Data Information:** Sufficiently detailed information about the data used to train the system so that a skilled person can build a substantially equivalent system. Data Information shall be made available under OSI-approved terms.
  - In particular, this must include: (1) the complete description of all data used for training, including (if used) of unshareable data, disclosing the provenance of the data, its scope and characteristics, how the data was obtained and selected, the labeling procedures, and data processing and filtering methodologies; (2) a listing of all publicly available training data and where to obtain it; and (3) a listing of all training data obtainable from third parties and where to obtain it, including for fee.
- **Code:** The complete source code used to train and run the system. The Code shall represent the full specification of how the data was processed and filtered, and how the training was done. Code shall be made available under OSI-approved licenses.
  - For example, if used, this must include code used for processing and filtering data, code used for training including arguments and settings used, validation and testing, supporting libraries like tokenizers and hyperparameters search code, inference code, and model architecture.
- **Parameters:** The model parameters, such as weights or other configuration settings. Parameters shall be made available under OSI-approved terms.
  - For example, this might include checkpoints from key intermediate stages of training as well as the final optimizer state.

The licensing or other terms applied to these elements and to any combination thereof may contain conditions that require any modified version to be released under the same terms as the original.




Q: What is the preferred form for making modifications to machine-learning systems?
Q: How important is comprehensive data information in modifying machine-learning systems?
Q: What type of data description is required for all data used in training machine-learning systems?



Summary: The section "Preferred form to make modifications to machine-learning systems" discusses the necessary components for altering machine-learning systems, highlighting the critical role of comprehensive data information accessible under OSI-approved terms.

Keywords: machine-learning systems, modifications, data information, OSI-approved terms, training data, unshareable data, accessibility, alterations, comprehensive description.

## Open Source models and Open Source weights

In this document, we delve into the intricacies of machine learning systems, specifically focusing on the components that constitute an AI model. Following our discussion on the architecture and inference code, we now turn our attention to the crucial elements of model parameters and weights. This section, titled "Open Source models and Open Source weights," elucidates the nature of AI weights as the learned parameters that enable the model to generate outputs from inputs. It also underscores the importance of open-source practices in modifying these components, emphasizing the need for transparency and accessibility in data information and code usage.


For machine learning systems,

- An **AI model** consists of the model architecture, model parameters (including weights) and inference code for running the model.
- **AI weights** are the set of learned parameters that overlay the model architecture to produce an output from a given input.

The preferred form to make modifications to machine learning systems also applies to these individual components. “Open Source models” and “Open Source weights” must include the data information and code used to derive those parameters.

The Open Source AI Definition does not require a specific legal mechanism for assuring that the model parameters are freely available to all. They may be free by their nature or a license or other legal instrument may be required to ensure their freedom. We expect this will become clearer over time, once the legal system has had more opportunity to address Open Source AI systems.




Q: What are the key components of an AI model discussed in this section?
Q: How do open source models and weights contribute to the functionality of AI systems?
Q: What role do model parameters and weights play in the generation of outputs from inputs in AI models?



Summary: This section, "Open Source models and Open Source weights," explains the concept of AI weights as learned parameters that allow models to produce outputs from inputs, emphasizing their role in open-source models.

Keywords: Open Source models, AI weights, learned parameters, model outputs, inputs, open-source, machine learning systems.

## Definitions

In this document, the "Definitions" section serves as a foundational reference for understanding key terms used throughout the content. It is strategically placed following the introduction to provide clarity on the terminology employed. This section elucidates the meaning of "AI system" and "machine learning", two pivotal concepts that underpin the discussion. The AI system definition outlines the capabilities and adaptability of machine-based systems, while the machine learning definition introduces the techniques that enable these systems to learn and improve over time.


- AI system[2](#833bf293-19d3-4c3c-97e0-1a284f4957dc) : An AI system is a machine-based system that, for explicit or implicit objectives, infers, from the input it receives, how to generate outputs such as predictions, content, recommendations, or decisions that can influence physical or virtual environments. Different AI systems vary in their levels of autonomy and adaptiveness after deployment.
- Machine learning[3](#86348933-d4a0-4115-b191-82675d1ac5db) : is a set of techniques that allows machines to improve their performance and usually generate models in an automated manner through exposure to training data, which can help identify patterns and regularities rather than through explicit instructions from a human. The process of improving a system’s performance using machine learning techniques is known as “training”.

1. These freedoms are derived from the [Free Software Definition](https://www.gnu.org/philosophy/free-sw.en.html) .[↩︎](#398e6e4c-5d98-4796-8bda-5bf97dc04a76-link)
2. [Recommendation of the Council on Artificial Intelligence OECD/LEGAL/0449, Organization for Economic and Co-operation Development (OECD), 2024](https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0449)[↩︎](#833bf293-19d3-4c3c-97e0-1a284f4957dc-link)
3. [Explanatory memorandum on the updated OECD definition of an AI system, OECD Artificial Intelligence Papers, No. 8, OECD Publishing, Paris](https://doi.org/10.1787/623da898-en)[↩︎](#86348933-d4a0-4115-b191-82675d1ac5db-link)


[See FAQs](https://opensource.org/ai/faq)[See Checklist](https://opensource.org/ai/checklist)[See list of endorsements](https://opensource.org/ai/endorsements)




Q: What is the purpose of the "Definitions" section in this document?
Q: How does the "Definitions" section contribute to understanding the content?
Q: What are the key terms defined in the "Definitions" section?



Summary: The "Definitions" section in this document clarifies the meanings of crucial terms such as "AI system" and "machine learning", providing a solid foundation for understanding the subsequent content.

Keywords: AI system, machine learning, terminology, foundational, understanding, capabilities, adaptability.

## Endorse the Open Source AI Definition

In this section, readers are invited to endorse the Open Source AI Definition. This endorsement serves as a public commitment to the principles outlined in the definition, which promote transparency, collaboration, and ethical use of artificial intelligence. By adding their name to the list of endorsers, individuals or organizations publicly align themselves with these values, fostering a community-driven approach to AI development and deployment.


[Add your name](https://opensource.org/ai/endorsements/endorse-the-open-source-ai-definition) to the list of endorsers.

Q: What is the purpose of endorsing the Open Source AI Definition?
Q: How does endorsing the Open Source AI Definition reflect on an individual or organization?
Q: What values does endorsing the Open Source AI Definition publicly align one with?


Summary: This section encourages readers to endorse the Open Source AI Definition, a public commitment to transparency, collaboration, and ethical AI use, fostering a community-driven approach to AI development and deployment.

Keywords: Open Source AI Definition, endorsement, transparency, collaboration, ethical AI, community-driven approach, AI development, AI deployment.
