package edu.project.sentiment;

import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
final class SentimentController {
    private final SentimentModel model;
    private final MeterRegistry metrics;
    private final String instance = System.getenv().getOrDefault("HOSTNAME", "local");

    SentimentController(SentimentModel model, MeterRegistry metrics) {
        this.model = model;
        this.metrics = metrics;
    }

    @GetMapping("/sentiment")
    ResponseEntity<Result> classify(@RequestParam String text) {
        if (text.isBlank() || text.length() > 2048) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Use 1–2048 characters");
        }
        String sentiment = model.predict(text);
        metrics.counter("sentiment.predictions", "label", sentiment).increment();
        return ResponseEntity.ok().header("X-Instance", instance).body(new Result(sentiment));
    }

    record Result(String sentiment) {}
}
