"""
Test data sets with sample IELTS Task 1 and Task 2 texts.
Provides realistic IELTS writing samples for comprehensive testing.

This module contains:
- Realistic IELTS writing samples for both Task 1 and Task 2
- Samples at different difficulty levels (beginner, intermediate, advanced)
- Edge cases for testing validation and error handling
- Mock OpenAI responses for different quality levels
- Utility functions for filtering and selecting test data
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class IELTSSample:
    """Sample IELTS writing text with metadata."""
    text: str
    task_type: str  # 'task_1' or 'task_2'
    word_count: int
    expected_band_range: tuple  # (min_band, max_band)
    description: str
    difficulty_level: str  # 'beginner', 'intermediate', 'advanced'


class IELTSTestData:
    """Collection of IELTS test samples for comprehensive testing."""
    
    # Task 1 Samples
    TASK_1_SAMPLES = [
        IELTSSample(
            text="""The bar chart shows the percentage of households with different types of internet connection from 2010 to 2020. Overall, there was a significant increase in broadband connections while dial-up connections decreased dramatically over the period.

In 2010, broadband connections accounted for 45% of households, while dial-up connections made up 35%. Mobile internet was relatively new at 15%, and fiber optic connections were minimal at just 5%.

By 2015, broadband had risen to 60% of households, becoming the dominant connection type. Dial-up connections fell sharply to 20%, while mobile internet grew to 25%. Fiber optic connections remained low at 10%.

The trend continued through 2020, with broadband reaching 70% of households. Dial-up connections nearly disappeared, dropping to just 5%. Mobile internet stabilized at 30%, while fiber optic connections showed the most dramatic growth, reaching 25% by the end of the period.

In conclusion, the data reveals a clear shift from traditional dial-up to modern broadband and emerging fiber optic technologies, with mobile internet maintaining steady growth throughout the decade.""",
            task_type='task_1',
            word_count=175,
            expected_band_range=(6.5, 7.5),
            description="Chart description with clear overview and data trends",
            difficulty_level='intermediate'
        ),
        
        IELTSSample(
            text="""The graph shows internet usage. Broadband went up from 2010 to 2020. Dial-up went down. Mobile internet also increased. Fiber optic was low but grew at the end.

In 2010 broadband was 45%. Dial-up was 35%. Mobile was 15%. Fiber was 5%.

2015 broadband was 60%. Dial-up was 20%. Mobile was 25%. Fiber was 10%.

2020 broadband was 70%. Dial-up was 5%. Mobile was 30%. Fiber was 25%.

So broadband increased the most. Dial-up decreased a lot. Mobile stayed steady. Fiber grew fast at the end.""",
            task_type='task_1',
            word_count=89,
            expected_band_range=(4.0, 5.5),
            description="Basic chart description with limited vocabulary and structure",
            difficulty_level='beginner'
        ),
        
        IELTSSample(
            text="""The bar chart delineates the evolutionary trajectory of household internet connectivity preferences across a decade-long period from 2010 to 2020, categorized into four distinct technological paradigms: traditional dial-up connections, broadband infrastructure, mobile internet platforms, and fiber optic networks.

A comprehensive analysis of the data reveals a pronounced paradigmatic shift in connectivity preferences, characterized by the precipitous decline of legacy dial-up technologies and the concomitant ascendancy of broadband and emerging fiber optic solutions. The initial configuration in 2010 demonstrated broadband's nascent dominance at 45% household penetration, while dial-up maintained substantial market presence at 35%. Mobile internet, representing the emergent wireless paradigm, captured 15% market share, with fiber optic technology maintaining a marginal 5% presence.

The intermediate period of 2015 witnessed an acceleration of these transformative trends, with broadband consolidating its market leadership through expansion to 60% household adoption. Simultaneously, dial-up experienced significant market contraction to 20%, while mobile internet demonstrated robust growth to 25%. Fiber optic technology, despite remaining relatively nascent at 10%, began exhibiting indicators of future expansion potential.

The culmination of this technological evolution by 2020 revealed broadband's sustained dominance at 70% household penetration, while dial-up connections experienced near-complete market obsolescence, declining to a mere 5%. Mobile internet achieved market stabilization at 30%, while fiber optic technology demonstrated the most remarkable growth trajectory, expanding quintuple-fold to achieve 25% market penetration.

In synthesis, the data illuminates a fundamental transformation in household connectivity infrastructure, characterized by the obsolescence of legacy technologies and the emergence of high-speed, high-capacity solutions that reflect contemporary digital consumption patterns and technological capabilities.""",
            task_type='task_1',
            word_count=287,
            expected_band_range=(7.5, 9.0),
            description="Advanced chart description with sophisticated vocabulary and complex structures",
            difficulty_level='advanced'
        )
    ]
    
    # Task 2 Samples
    TASK_2_SAMPLES = [
        IELTSSample(
            text="""Education is one of the most important aspects of human development. I believe that governments should provide free education to all citizens because it promotes equality and economic growth.

Firstly, free education ensures that everyone has equal opportunities regardless of their financial background. This helps create a more fair society where success is based on merit rather than wealth. When education is expensive, only wealthy families can afford quality schooling, which perpetuates social inequality. Free education breaks this cycle and gives everyone a chance to succeed.

Secondly, educated populations contribute more to economic development through innovation and productivity. Countries with higher education levels tend to have stronger economies and better living standards. When people are educated, they can develop new technologies, start businesses, and contribute to their communities in meaningful ways.

However, some argue that free education is too expensive for governments to provide. While this is a valid concern, the long-term benefits outweigh the costs. The economic returns from an educated population far exceed the initial investment in education infrastructure and teacher salaries.

In conclusion, free education is essential for creating equal opportunities and promoting economic growth. Governments should prioritize education funding as an investment in their country's future prosperity and social cohesion.""",
            task_type='task_2',
            word_count=201,
            expected_band_range=(6.0, 7.0),
            description="Balanced argument essay with clear structure and examples",
            difficulty_level='intermediate'
        ),
        
        IELTSSample(
            text="""Technology is good and bad. Some people like it and some don't. I think technology is mostly good but has some problems.

Technology helps us do things faster. We can talk to people far away with phones and computers. We can find information quickly on the internet. This makes life easier and more convenient.

But technology also causes problems. People spend too much time on phones and don't talk to each other. Some people lose their jobs because machines do their work. Also, technology can be expensive and not everyone can buy it.

I think the good things about technology are more than the bad things. We just need to use it carefully and not too much. We should still talk to people in person and not always use phones.

In conclusion, technology is helpful but we need to be careful how we use it. It can make life better if we use it right.""",
            task_type='task_2',
            word_count=145,
            expected_band_range=(4.5, 5.5),
            description="Basic opinion essay with simple vocabulary and limited development",
            difficulty_level='beginner'
        ),
        
        IELTSSample(
            text="""The inexorable advancement of technological innovation has fundamentally transformed the contemporary human experience, precipitating a paradigmatic shift in how individuals interact, work, and conceptualize their relationship with the digital ecosystem. While technological proliferation has undeniably enhanced human capabilities and facilitated unprecedented global connectivity, it has simultaneously engendered multifaceted challenges that warrant critical examination and nuanced consideration.

The proponents of technological advancement articulate compelling arguments regarding its transformative potential for human flourishing. Digital technologies have democratized access to information, enabling individuals from diverse socioeconomic backgrounds to acquire knowledge and skills previously accessible only to privileged elites. Furthermore, technological innovations in healthcare, communication, and transportation have substantially improved quality of life indicators across multiple demographic segments. The emergence of artificial intelligence and machine learning algorithms has augmented human cognitive capabilities, facilitating more efficient problem-solving and decision-making processes across various professional domains.

Conversely, the critics of unbridled technological adoption raise legitimate concerns regarding its deleterious effects on social cohesion, employment stability, and psychological well-being. The proliferation of social media platforms has paradoxically increased social isolation while ostensibly enhancing connectivity, contributing to rising rates of anxiety, depression, and interpersonal dysfunction among digital natives. Additionally, automation and artificial intelligence threaten to displace significant portions of the workforce, potentially exacerbating existing socioeconomic inequalities and creating unprecedented challenges for labor market adaptation.

The environmental implications of technological advancement present another dimension of complexity, as the production and disposal of electronic devices contribute substantially to ecological degradation and resource depletion. The carbon footprint associated with data centers and digital infrastructure raises questions about the sustainability of current technological consumption patterns.

In synthesizing these competing perspectives, I contend that technological advancement represents a double-edged phenomenon that requires sophisticated regulatory frameworks and ethical guidelines to maximize benefits while mitigating potential harms. Rather than embracing technological determinism or rejecting innovation entirely, society must cultivate a more nuanced approach that prioritizes human welfare, environmental sustainability, and equitable access to technological benefits.

Ultimately, the trajectory of technological development should be guided by humanistic principles that preserve social cohesion, protect vulnerable populations, and ensure that technological progress serves the collective good rather than merely advancing narrow commercial interests.""",
            task_type='task_2',
            word_count=367,
            expected_band_range=(8.0, 9.0),
            description="Sophisticated argument essay with advanced vocabulary and complex analysis",
            difficulty_level='advanced'
        ),
        
        IELTSSample(
            text="""Climate change is a serious problem that affects everyone. Many people think that governments should take action to solve this problem. I agree with this opinion because climate change is too big for individuals to solve alone.

Governments have the power and resources to make significant changes. They can create laws to reduce pollution and invest in renewable energy. For example, they can require companies to use cleaner technologies and provide subsidies for solar and wind power. Individual people cannot do these big things by themselves.

However, individuals also have a role to play in fighting climate change. We can reduce our carbon footprint by using less energy, driving less, and choosing sustainable products. When many people make these small changes, it can have a big impact.

Some people argue that government action is too expensive and will hurt the economy. But I think the cost of not acting is much higher. Climate change will cause floods, droughts, and other disasters that will cost much more money than prevention.

In conclusion, both governments and individuals need to work together to address climate change effectively. Governments should lead with policies and investments, while individuals should support these efforts through their daily choices.""",
            task_type='task_2',
            word_count=195,
            expected_band_range=(6.0, 6.5),
            description="Opinion essay with clear position and supporting arguments",
            difficulty_level='intermediate'
        )
    ]
    
    # Edge cases for testing
    EDGE_CASE_SAMPLES = [
        IELTSSample(
            text="This text is too short for IELTS evaluation.",
            task_type='task_2',
            word_count=9,
            expected_band_range=(0.0, 0.0),
            description="Text too short - should trigger validation error",
            difficulty_level='invalid'
        ),
        
        IELTSSample(
            text="Esta es una muestra de texto en español que debería ser detectada como no inglés por el sistema de validación. El texto tiene suficientes palabras para pasar la validación de longitud, pero debería fallar en la detección de idioma. Este tipo de casos edge son importantes para probar la robustez del sistema de evaluación.",
            task_type='task_2',
            word_count=52,
            expected_band_range=(0.0, 0.0),
            description="Non-English text - should trigger language validation error",
            difficulty_level='invalid'
        ),
        
        IELTSSample(
            text="""This is an ambiguous text that could potentially be either Task 1 or Task 2 depending on interpretation. It discusses various topics without clear indicators of whether it's describing data or presenting an argument. The content is neutral and doesn't contain specific Task 1 phrases like "the chart shows" or Task 2 phrases like "I believe" or "in my opinion". This type of text is designed to test the task type detection system's ability to handle unclear cases and request clarification from users when necessary. The text has sufficient length to pass basic validation but lacks clear task type indicators that would allow automatic classification.""",
            task_type='ambiguous',
            word_count=108,
            expected_band_range=(0.0, 0.0),
            description="Ambiguous text - should trigger task type clarification",
            difficulty_level='ambiguous'
        )
    ]
    
    @classmethod
    def get_task1_samples(cls) -> List[IELTSSample]:
        """Get all Task 1 samples."""
        return cls.TASK_1_SAMPLES
    
    @classmethod
    def get_task2_samples(cls) -> List[IELTSSample]:
        """Get all Task 2 samples."""
        return cls.TASK_2_SAMPLES
    
    @classmethod
    def get_edge_cases(cls) -> List[IELTSSample]:
        """Get edge case samples."""
        return cls.EDGE_CASE_SAMPLES
    
    @classmethod
    def get_all_samples(cls) -> List[IELTSSample]:
        """Get all samples including edge cases."""
        return cls.TASK_1_SAMPLES + cls.TASK_2_SAMPLES + cls.EDGE_CASE_SAMPLES
    
    @classmethod
    def get_samples_by_difficulty(cls, difficulty: str) -> List[IELTSSample]:
        """Get samples filtered by difficulty level."""
        all_samples = cls.get_all_samples()
        return [sample for sample in all_samples if sample.difficulty_level == difficulty]
    
    @classmethod
    def get_samples_by_band_range(cls, min_band: float, max_band: float) -> List[IELTSSample]:
        """Get samples within specified band score range."""
        all_samples = cls.TASK_1_SAMPLES + cls.TASK_2_SAMPLES  # Exclude edge cases
        return [
            sample for sample in all_samples 
            if sample.expected_band_range[0] >= min_band and sample.expected_band_range[1] <= max_band
        ]


# Mock OpenAI responses for different sample types
MOCK_OPENAI_RESPONSES = {
    'high_quality': {
        "task_achievement_score": 7.5,
        "coherence_cohesion_score": 7.0,
        "lexical_resource_score": 8.0,
        "grammatical_accuracy_score": 7.0,
        "overall_band_score": 7.5,
        "detailed_feedback": "This is a well-structured response that effectively addresses the task requirements with clear arguments and good examples.",
        "improvement_suggestions": [
            "Use more varied sentence structures to enhance flow",
            "Include more specific examples to support arguments",
            "Work on minor grammatical accuracy issues"
        ],
        "score_justifications": {
            "task_achievement": "Fully addresses all parts of the task with clear position",
            "coherence_cohesion": "Well organized with effective use of cohesive devices",
            "lexical_resource": "Wide range of vocabulary used accurately and appropriately",
            "grammatical_accuracy": "Good range of structures with minor errors"
        }
    },
    
    'medium_quality': {
        "task_achievement_score": 6.0,
        "coherence_cohesion_score": 6.5,
        "lexical_resource_score": 6.0,
        "grammatical_accuracy_score": 5.5,
        "overall_band_score": 6.0,
        "detailed_feedback": "The response addresses the task adequately but could benefit from more detailed development and clearer examples.",
        "improvement_suggestions": [
            "Develop ideas more fully with specific examples",
            "Improve grammatical accuracy and sentence variety",
            "Use more precise vocabulary choices"
        ],
        "score_justifications": {
            "task_achievement": "Addresses the task but some aspects could be more fully developed",
            "coherence_cohesion": "Generally well organized with adequate linking",
            "lexical_resource": "Adequate vocabulary range with some inaccuracies",
            "grammatical_accuracy": "Mix of simple and complex structures with some errors"
        }
    },
    
    'low_quality': {
        "task_achievement_score": 4.5,
        "coherence_cohesion_score": 4.0,
        "lexical_resource_score": 4.5,
        "grammatical_accuracy_score": 4.0,
        "overall_band_score": 4.5,
        "detailed_feedback": "The response attempts to address the task but lacks development and contains several errors that impede communication.",
        "improvement_suggestions": [
            "Develop ideas more clearly with better examples",
            "Improve sentence structure and grammar",
            "Use more varied and accurate vocabulary",
            "Work on overall organization and coherence"
        ],
        "score_justifications": {
            "task_achievement": "Attempts to address task but lacks adequate development",
            "coherence_cohesion": "Some organization present but lacks clear progression",
            "lexical_resource": "Limited vocabulary range with frequent errors",
            "grammatical_accuracy": "Limited range of structures with frequent errors"
        }
    }
}