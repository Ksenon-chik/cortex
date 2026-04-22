import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.forecast import PredictionAgent
from app.agents.schemas import AnalysisResult, PredictionOutput, SearchFindings


@pytest.fixture
def mock_tavily_response():
    return {
        "answer": "Test AI summary",
        "results": [
            {
                "title": "Test Article",
                "url": "https://test.com/article",
                "content": "Test content",
                "score": 0.9,
            }
        ],
    }


@pytest.fixture
def mock_openrouter_response():
    message = MagicMock()
    message.content = json.dumps({
        "key_factors": ["factor1"],
        "sentiment": "neutral",
        "summary": "probability of 75% based on analysis",
    })
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def mock_openrouter_prediction():
    message = MagicMock()
    message.content = json.dumps({
        "probability": 0.75,
        "verdict": "yes",
        "reasoning": "Based on analysis",
        "confidence": 0.8,
    })
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture
def agent():
    return PredictionAgent(tavily_api_key="test-tavily", openrouter_api_key="test-or")


class TestPredictionAgentResearch:
    async def test_research_returns_findings(self, agent, mock_tavily_response):
        agent.tavily.search = AsyncMock(return_value=mock_tavily_response)
        result = await agent.research("Test Event", "Test description")
        assert isinstance(result, SearchFindings)
        assert result.answer == "Test AI summary"
        assert len(result.results) == 1
        assert result.results[0]["title"] == "Test Article"

    async def test_research_fallback_on_empty(self, agent):
        agent.tavily.search = AsyncMock(side_effect=[
            {"results": []},
            {"answer": "fallback", "results": [{"title": "Fallback", "url": "https://x.com", "content": "c", "score": 0.5}]},
        ])
        result = await agent.research("Test Event", "desc")
        assert len(result.results) == 1
        assert result.results[0]["title"] == "Fallback"
        assert agent.tavily.search.call_count == 2


class TestPredictionAgentAnalyze:
    async def test_analyze_returns_analysis(self, agent, mock_openrouter_response):
        agent.openrouter.chat.send_async = AsyncMock(return_value=mock_openrouter_response)
        findings = SearchFindings(query="test", answer="summary", results=[{"title": "T", "url": "https://t.com", "content": "c", "score": 0.9}])
        result = await agent.analyze(findings, "Event", "desc", ["Yes", "No"])
        assert isinstance(result, AnalysisResult)
        assert result.sentiment == "neutral"
        assert "probability" in result.summary.lower() or "75" in result.summary


class TestPredictionAgentPredict:
    async def test_predict_returns_output(self, agent, mock_openrouter_prediction):
        agent.openrouter.chat.send_async = AsyncMock(return_value=mock_openrouter_prediction)
        analysis = AnalysisResult(key_factors=["factor1"], sentiment="bullish", summary="good")
        result = await agent.predict(analysis, "google/gemini-2.0-flash-exp:free", ["Yes", "No"])
        assert isinstance(result, PredictionOutput)
        assert result.probability == 0.75
        assert result.verdict == "yes"
        assert result.model_name == "google/gemini-2.0-flash-exp:free"

    async def test_predict_json_fallback(self, agent):
        message = MagicMock()
        message.content = 'probability: 0.65 verdict: yes some extra text confidence: 0.7'
        choice = MagicMock()
        choice.message = message
        agent.openrouter.chat.send_async = AsyncMock(return_value=MagicMock(choices=[choice]))

        analysis = AnalysisResult(key_factors=[], sentiment="neutral", summary="x")
        result = await agent.predict(analysis, "test-model", ["Yes", "No"])
        assert result.probability == 0.65
        assert result.verdict == "yes"

    async def test_predict_probability_clamped(self, agent):
        message = MagicMock()
        message.content = json.dumps({"probability": 1.5, "verdict": "yes", "reasoning": "x", "confidence": 0.5})
        choice = MagicMock()
        choice.message = message
        agent.openrouter.chat.send_async = AsyncMock(return_value=MagicMock(choices=[choice]))

        analysis = AnalysisResult(key_factors=[], sentiment="neutral", summary="x")
        result = await agent.predict(analysis, "test-model", ["Yes", "No"])
        assert result.probability == 1.0


class TestPredictionAgentPipeline:
    async def test_generate_forecast_full_pipeline(self, agent):
        agent.tavily.search = AsyncMock(return_value={
            "answer": "summary",
            "results": [{"title": "T", "url": "https://t.com", "content": "c", "score": 0.9}],
        })
        agent.openrouter.chat.send_async = AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(
                content=json.dumps({"key_factors": ["f1"], "sentiment": "bullish", "summary": "good"})
            ))]
        ))

        result = await agent.generate_forecast("Event", "desc", "google/gemini-2.0-flash-exp:free", ["Yes", "No"])
        assert isinstance(result, PredictionOutput)
        assert result.probability == 0.75 or result.probability == 0.5
