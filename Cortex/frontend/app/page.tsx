import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Brain, BarChart3, Trophy } from "lucide-react";

const features = [
  {
    icon: Brain,
    title: "AI Predictions",
    description: "Multiple LLM models research events, analyze news, and generate probability forecasts with cited sources.",
  },
  {
    icon: BarChart3,
    title: "Brier Score Tracking",
    description: "Every prediction is scored. Lower Brier Score means better calibrated probabilities — see which models are actually accurate.",
  },
  {
    icon: Trophy,
    title: "Model Leaderboard",
    description: "Public rankings show which AI models consistently predict correctly. No hype, just data.",
  },
];

export default function HomePage() {
  return (
    <div className="container mx-auto px-4 py-12 max-w-6xl">
      {/* Hero */}
      <section className="text-center mb-16">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
          Which AI Models Actually Predict the Future?
        </h1>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-8">
          Cortex tracks predictions from multiple AI models against real-world outcomes.
          See Brier Scores, compare accuracy, and find out which models you can trust.
        </p>
        <div className="flex gap-4 justify-center">
          <Link href="/events">
            <Button size="lg">Browse Events</Button>
          </Link>
          <Link href="/leaderboard">
            <Button size="lg" variant="outline">View Leaderboard</Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="grid md:grid-cols-3 gap-6 mb-16">
        {features.map((feature) => (
          <Card key={feature.title}>
            <CardHeader>
              <feature.icon className="w-8 h-8 mb-2 text-primary" />
              <CardTitle>{feature.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-base">{feature.description}</CardDescription>
            </CardContent>
          </Card>
        ))}
      </section>

      {/* CTA */}
      <section className="text-center border rounded-lg p-8 bg-muted/30">
        <h2 className="text-2xl font-semibold mb-2">Start Generating Forecasts</h2>
        <p className="text-muted-foreground mb-4">
          Register for free and generate forecasts with top AI models. 5 free forecasts per day.
        </p>
        <Link href="/register">
          <Button size="lg">Get Started Free</Button>
        </Link>
      </section>
    </div>
  );
}
