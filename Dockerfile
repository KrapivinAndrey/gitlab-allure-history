FROM mwendler/wget as download

ARG ALLURE_VERSION=2.13.9

RUN wget --no-check-certificate https://repo.maven.apache.org/maven2/io/qameta/allure/allure-commandline/$ALLURE_VERSION/allure-commandline-$ALLURE_VERSION.tgz \
	&& tar -zxf allure-commandline-$ALLURE_VERSION.tgz \
	&& mv /allure-$ALLURE_VERSION /allure

FROM python:3.7.9-alpine3.13 AS build-image

COPY --from=download /allure /allure
COPY generate-index.py /usr/

RUN apk --no-cache add \
		git \
		openjdk8-jre=8.275.01-r0 \
    && rm -rf /var/cache/apk/*

ENV PATH="/allure/bin:/app/venv/bin:${PATH}"

WORKDIR /app
