package edu.project.sentiment;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
final class SentimentModel {
    private static final Pattern WORD = Pattern.compile("[\\p{L}]+");
    private static final List<String> LABELS = List.of("neutral", "positive", "negative");
    private final List<Distribution> model;

    SentimentModel() throws IOException {
        Map<String, Map<String, Integer>> counts = new HashMap<>();
        Map<String, Integer> vocabulary = new HashMap<>();
        LABELS.forEach(label -> counts.put(label, new HashMap<>()));
        try (var reader = new BufferedReader(new InputStreamReader(
                SentimentModel.class.getResourceAsStream("/sentiment.tsv"), StandardCharsets.UTF_8))) {
            for (String line; (line = reader.readLine()) != null;) {
                String[] row = line.split("\\t", 2);
                for (String word : words(row[1])) {
                    counts.get(row[0]).merge(word, 1, Integer::sum);
                    vocabulary.merge(word, 1, Integer::sum);
                }
            }
        }
        var distributions = new ArrayList<Distribution>();
        for (String label : LABELS) {
            var countsForLabel = counts.get(label);
            int total = countsForLabel.values().stream().mapToInt(Integer::intValue).sum();
            double denominator = total + vocabulary.size();
            Map<String, Double> logLikelihood = new HashMap<>();
            vocabulary.keySet().forEach(word -> logLikelihood.put(word,
                    Math.log((countsForLabel.getOrDefault(word, 0) + 1) / denominator)));
            distributions.add(new Distribution(label, Map.copyOf(logLikelihood)));
        }
        model = List.copyOf(distributions);
    }

    String predict(String text) {
        List<String> tokens = words(text);
        Distribution best = model.getFirst();
        double bestScore = Double.NEGATIVE_INFINITY;
        for (Distribution candidate : model) {
            double score = 0;
            for (String token : tokens) {
                score += candidate.logLikelihood().getOrDefault(token, 0.0);
            }
            if (score > bestScore) {
                best = candidate;
                bestScore = score;
            }
        }
        return best.label();
    }

    private static List<String> words(String text) {
        return WORD.matcher(text.toLowerCase(Locale.ROOT)).results().map(match -> match.group()).toList();
    }

    private record Distribution(String label, Map<String, Double> logLikelihood) {}
}
