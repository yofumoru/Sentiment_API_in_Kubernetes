FROM maven:3.9-eclipse-temurin-21-alpine AS build
WORKDIR /workspace
COPY pom.xml .
COPY src ./src
RUN mvn -B -ntp package
RUN jlink --add-modules java.se,jdk.unsupported,jdk.management,jdk.crypto.ec \
    --strip-debug --no-header-files --no-man-pages --compress=zip-6 --output /opt/runtime

FROM alpine:3.22
RUN apk add --no-cache libstdc++ zlib
WORKDIR /app
COPY --from=build /opt/runtime /opt/java
COPY --from=build /workspace/target/sentiment.jar /app/sentiment.jar
USER 10001:10001
EXPOSE 8080 8081
ENTRYPOINT ["/opt/java/bin/java", "-XX:MaxRAMPercentage=65", "-jar", "/app/sentiment.jar"]
