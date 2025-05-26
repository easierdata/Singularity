# Preserving Open Science Data with Singularity and Docker: A Step-by-Step Guide

In today’s fast-changing digital landscape, **data integrity and preservation** are more critical than ever. As open science research accelerates, the risk of valuable datasets disappearing grows—making it essential to store, share, and safeguard data for the long term. The [Filecoin](https://filecoin.io/) network offers decentralized, reliable storage, and tools like [Singularity](https://data-programs.gitbook.io/singularity) make onboarding data to Filecoin accessible and efficient.

This guide will show you how to deploy and use Singularity within a Docker container environment, leveraging a pre-built [Docker image](https://hub.docker.com/repository/docker/sethdd/singularity/general). We’ll walk through building the image, configuring your environment, running the service with Docker Compose, and using the Singularity API to prepare your data for Filecoin storage.

> If you're a Docker wizard and looking for the docker-compose file, you can find it [here](../Utilities/docker/docker-compose-all-services.yml). Otherwise, this guide is for you! It’s designed to help you get started with Singularity and Docker, even if you have no prior experience with these tools.

---

## Table of Contents

- [Preserving Open Science Data with Singularity and Docker: A Step-by-Step Guide](#preserving-open-science-data-with-singularity-and-docker-a-step-by-step-guide)
  - [Table of Contents](#table-of-contents)
  - [Why Singularity + Docker?](#why-singularity--docker)
  - [Prerequisites](#prerequisites)
  - [Configuring with .env](#configuring-with-env)
  - [Overview of the Dockerfile](#overview-of-the-dockerfile)
  - [The Entrypoint Script](#the-entrypoint-script)
  - [Deploying with Docker Compose](#deploying-with-docker-compose)
  - [Volume Mounts and Data Persistence](#volume-mounts-and-data-persistence)
  - [Running and Managing Containers](#running-and-managing-containers)
  - [Using the Singularity API](#using-the-singularity-api)
  - [Caveats \& Tips](#caveats--tips)
  - [Troubleshooting and FAQ](#troubleshooting-and-faq)
  - [Additional Resources](#additional-resources)
  - [Conclusion](#conclusion)

---

## Why Singularity + Docker?

Singularity is a robust tool for preparing and packing data into **CAR files** (Content Addressable aRchives), which are essential for making deals with Filecoin storage providers. Running Singularity in Docker offers several advantages:

- **Isolation:** Keeps your host system clean and dependencies managed.
- **Reproducibility:** Ensures consistent environments across teams and deployments.
- **Scalability:** Easily scale up or down as your data onboarding needs change.

Most of all, you can customize docker images are customizable to suit your specific needs. This alone has helped me quickly get up and running on different systems with a Singularity instance and not having to worry about building the binary, downloading dependencies, setting up my environment, etc.  Automation is key to reproducibility 😉

---

## Prerequisites

Before you begin, make sure you have:

- **Singularity installed** ([installation guide](https://data-programs.gitbook.io/singularity/installation/download-binaries))
- **Docker** installed ([installation guide](https://docs.docker.com/get-docker/))
- **Docker Compose** installed ([installation guide](https://docs.docker.com/compose/install/))
- **Basic command-line skills**

## Configuring with .env

I want to start by outlining the `.env` file. The [dockerfile](../Utilities/docker/dockerfile) and [docker-compose file](../Utilities/docker/docker-compose.yml) have been configured with default values for the environment variables but you can override them without editing the files directly. Super helpful when it comes to adding additional singularity service workers to the docker-compose file.

You can copy the contents of the sample `.env` file found [here](../Utilities/docker/.env-example) and get an idea of each variable in the table below.

| variable             | default value              | description                                     |
| -------------------- | -------------------------- | ----------------------------------------------- |
| `POSTGRES_USER`      | `postgres`                 | The username for the PostgreSQL database.       |
| `POSTGRES_PASSWORD`  | `postgres`                 | The password for the PostgreSQL database.       |
| `DB_NAME`            | `singularity`              | The name of the database.                       |
| `APP_DIR`            | `/path/to/mount/volume/mount`[^1] | The application directory path for volume mounting. |
| `DB_PORT`            | `5555`                     | The port number for the database connection.    |
| `SINGULARITY_API_PORT` | `9090`                   | The port number for the Singularity API.        |
| `DB_HOSTNAME`        | `db` [^2]                        | The hostname for the database service.          |
| `PUID`               | `1000`                     | The user ID for process execution.              |
| `PGID`               | `1000`                     | The group ID for process execution.             |
| `UMASK`              | `022`                      | The umask for file permissions.                 |
| `GOLOG_LOG_LEVEL`    | `info`                     | The logging level for Golog.                    |
| `GOLOG_LOG_FMT`      | `color`                    | The logging format for Golog.                   |

> Environment variables (except for variables such as `POSTGRES_PASSWORD` and `POSTGRES_USER`) are added to your `.bashrc` file so you can easily access them when you exec into the container and persist across container restarts.

Since the docker image is intended to run alongside a PostgreSQL database container, the database connection string is built and saved to the `DATABASE_CONNECTION_STRING` environment variable. Singularity will automatically use this variable to connect to the database. This is really useful since you can quickly run singularity commands without having to worry about passing in the connection string like this:

```bash
singularity --database-connection-string=postgres://postgres:postgres@db:5555/singularity 
```

[^1]: **Note:** The `APP_DIR` variable is used to set the application directory path for [volume mounting](https://docs.docker.com/engine/storage/volumes/). This is important for persisting data like our Postgres database instance.

[^2]: **Note:** The `DB_HOSTNAME` variable is used to set the hostname for the database service. This is important for ensuring that the Singularity service can connect to the database correctly. The default value is `db`, which matches the service name in the Docker Compose file. If you change the value of `DB_HOSTNAME`, make sure to update the corresponding service name in the Docker Compose file as well.

---

## Overview of the Dockerfile

We've built and maintain a docker image for Singularity that's hosted at [Docker Hub](https://hub.docker.com/repository/docker/sethdd/singularity/general). One of the main reasons we built our own image is to streamline some of the essential installation steps and dependencies.

> **Note:** The Singularity image is intended to be used with docker-compose as a service alongside a PostgreSQL database. While the image could run as a standalone container, [it is not recommended](https://data-programs.gitbook.io/singularity/installation/deploy-to-production) since the default database backend is `sqlite3` and does not support [concurrent writes](https://data-programs.gitbook.io/singularity/faq/database-is-locked).

I often need to execute into the container to run singularity commands but since the binary path is not in the path, I have to run commands via `/app/singularity` which is not ideal. The `nano` editor has also been added to the image as to easily edit files when inside the container, this is especially useful when needing to edit the `bashrc` file or other configuration files.

If you want to customize the image, you can do so using the provided [Dockerfile](../Utilities/docker/dockerfile). As noted in [above](#configuring-with-env), the `.env` file can be used to override default variables for your Docker setup.

**Building the Image from Scratch:**

Assuming you have the Dockerfile in the current directory, you can build the image with:

```bash
docker build -t <image name> .
```

If you want to upload the image to Docker Hub, you can do so with the following command:

```bash
docker tag <image name> <docker hub username>/<image name>:<tag>
```

Then push the image to Docker Hub:

```bash
docker push <docker hub username>/<image name>:<tag>
```

**Example:**

```bash
docker build -t singularity .
docker tag singularity easierdata/singularity:latest
docker push easierdata/singularity:latest
```

More information on building and pushing Docker images can be found in the [Docker documentation](https://docs.docker.com/get-started/introduction/build-and-push-first-image/).

---

## The Entrypoint Script

> TLDR: In essence, the script acts as a flexible bootstrapper for the Singularity containers, adapting the startup behavior based on environment variables and ensuring a consistent operational environment.

One unique feature that I've added to the image is the [`ENTRYPOINT` script](../Utilities/docker/scripts), serving as the initial process, accepting commands, that runs when a Docker container starts. Its primary functions are:

1. **Environment Configuration**:
    - It ensures that the `DATABASE_CONNECTION_STRING` environment variable is properly set. It checks for `DATABASE_CONNECTION_STRING` or a fallback `DB_STRING` passed from the Docker environment (e.g., via `docker-compose.yml` or `.env` file).
    - It exports this `DATABASE_CONNECTION_STRING` and also appends it to the `/home/appuser/.bashrc` file. This makes the connection string readily available for any interactive shell sessions within the container and ensures it persists for the Singularity application.

2. **Conditional Database Initialization**:
    - The script checks for an environment variable `RUN_SINGULARITY_INIT`.
    - If `RUN_SINGULARITY_INIT` is set to `"true"`, the script executes the `singularity admin init` command. This command initializes the database schema required by Singularity. After a successful (or failed) initialization, the script exits. This behavior is key for the `singularity_init` service in your `docker-compose.yml`, allowing it to run once and complete.

3. **Executing Singularity `run` Commands**:
    - If `RUN_SINGULARITY_INIT` is not `"true"`, the script proceeds to execute whatever command is passed to the container. This is typically defined by the `CMD` instruction in the Dockerfile or the `command` field in a `docker-compose.yml` service definition (e.g., `singularity run api --bind :9090`). The `exec "$@"` line achieves this, replacing the script process with the main command.

**How it Streamlines Docker Compose Orchestration:**

- **Reusable Image**: It allows you to use the *same* Docker image for different roles within your `docker-compose.yml`. For instance, the `init` command runs the database initialization, the `api` command runs the Singularity API service, and the `dataset-worker` command runs the dataset preparation service. The behavior is differentiated by the `RUN_SINGULARITY_INIT` environment variable.

- **Centralized Logic**: Common setup tasks, like configuring the database connection string, are handled in one place (the script via the `.env` file) rather than being duplicated or managed separately for each service.

- **Simplified Service Definition**: The `docker-compose.yml` services can be simpler. The `singularity_init` service, for example, only needs to set `RUN_SINGULARITY_INIT: "true"`; the script handles the rest of the initialization logic.

---

## Deploying with Docker Compose

Singularity is designed as a [Database Abstraction Layer](https://en.wikipedia.org/wiki/Database_abstraction_layer), containing different [components](https://data-programs.gitbook.io/singularity/cli-reference/run) that each run as a service. This is where Docker Compose comes in handy since we can configure our docker-compose file to run multiple services.

The following example shows a basic setup with a PostgreSQL database and two Singularity services.

```yaml
name: singularity-instance
services:
  db:
    container_name: Main-DB
    image: postgres:17
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -h localhost"]
      interval: 5s
      timeout: 5s
      retries: 5
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${DB_NAME:-singularity}
    volumes:
      - ${APP_DIR:-.}/postgres_db:/var/lib/postgresql/data
      - ${APP_DIR:-.}/sample_data:/data
    ports:
      - ${DB_PORT:-5433}:5432
    networks:
      - db-net

  singularity_init:
    container_name: Singularity-INIT
    image: sethdd/singularity:latest
    environment:
      # Tell the entrypoint script to run the init command
      RUN_SINGULARITY_INIT: "true"
      DB_HOSTNAME: db # Ensure this matches the db service name
      # POSTGRES_USER, POSTGRES_PASSWORD, DB_NAME inherited from .env or Dockerfile defaults
    restart: on-failure
    depends_on:
      db:
        condition: service_healthy
    networks:
      - db-net

  singularity_api:
    container_name: SingularityAPI
    image: sethdd/singularity:latest
    volumes:
      - ${APP_DIR:-.}/config:/home/appuser/config
      - ${APP_DIR:-.}/sample_data:/data
    # This command will be passed to the entrypoint script via 'exec "$@"'
    command: singularity run api --bind :9090
    ports:
      - ${SINGULARITY_API_PORT:-9090}:9090
    environment:
      DB_HOSTNAME: db # Ensure this matches the db service name
      # Pass necessary DB connection details (can also rely on defaults set in Dockerfile ENV)
      # POSTGRES_USER, POSTGRES_PASSWORD, DB_NAME inherited from .env or Dockerfile defaults
    restart: always
    depends_on:
      db:
        condition: service_healthy
      singularity_init:
        # Wait for the init service to complete successfully
        condition: service_completed_successfully
    networks:
      - db-net

networks:
  db-net:
    driver: bridge
```

**Key Components:**

- **db:** PostgreSQL database service.
  - Uses the official `postgres` image.
  - Health checks ensure the database is ready before other services start.
  - Volumes for data persistence and sample data.
- **singularity_init:** Initializes the Singularity database.
  - Setting the `RUN_SINGULARITY_INIT` env variable to true the Runs the `init` command to set up the database schema.
  - Depends on the `db` service being healthy.
- **singularity_api:** The Singularity API service.
  - Setting the `command` element to run the Singularity API on port `9090`.
  - Binds the `/data` directory for data access.
  - Depends on both `db` and `singularity_init` services.
- **Networks:** All services are connected to a custom bridge network (`db-net`) for communication.

The above docker-compose example can be found [here](../Utilities/docker/docker-compose.yml) and another compose file [here](../Utilities/docker/docker-compose-all-services.yml) configured with all the necessary Singularity services for data preparation and deal making.

Check out the [compose file reference guide](https://docs.docker.com/reference/compose-file/) for more details on the configuration options available.

---

## Volume Mounts and Data Persistence

The `/data` volume mount points to a local directory to:

- reference sample data that you would like to [prepare](https://data-programs.gitbook.io/singularity/cli-reference/storage/create/local) with Singularity.
- store the output CAR files from a preparation. [Creating output CARs](https://data-programs.gitbook.io/singularity/cli-reference/prep/attach-output) is entirely optional. Singularity defaults to [Inline Preparation](https://data-programs.gitbook.io/singularity/topics/inline-preparation), conserving storage space.

**Example Volume Mount:**

```yaml
volumes:
  - /absolute/path/to/mydata:/data
```

Inside the container, `/data` will point to your dataset.

---

## Running and Managing Containers

**Start your stack:**

```bash
docker compose -f /path/to/docker-compose.yaml up -d
```

Setting the `-d` flag runs the containers in detached mode. This allows you to run the containers in the background and continue using your terminal session.

**Gracefully stop containers:**

```bash
docker compose -f /path/to/docker-compose.yaml down
```

This command stops and removes all containers defined in the `docker-compose.yaml` file.

**Check container status:**

```bash
docker-compose ps
```

**Access a running container:**

```bash
docker exec -it <container_name> /bin/bash
```

This command opens a shell inside the specified container, allowing you to run commands directly.

*If `bash` isn’t available, try `sh`.*

*Other Common Commands:*

- `docker-compose logs -f` (view logs)
- `docker-compose restart <container_name>` (restart the service)

---

## Using the Singularity API

Once running, Singularity exposes an HTTP API (default port `9090`), where you can interact with the service programmatically with tools like `curl` or Postman.

**Swagger UI:**
For interactive API exploration, visit:
`http://localhost:9090/swagger/index.html`

Check out the [Singularity API Reference](https://data-programs.gitbook.io/singularity/web-api-reference) for detailed information on available endpoints.

---

## Caveats \& Tips

- **Permissions:**
Ensure the Docker container user has read/write access to the mounted directory.

> Tip: Use `chown` or set appropriate UID/GID in the Dockerfile if needed.

- **SELinux/AppArmor:**
On some systems, you may need to add `:z` or `:Z` to the volume mount for SELinux compatibility.

*Common error: “Permission denied”*
Solution: `sudo chown -R 1000:1000 /absolute/path/to/mydata`

## Troubleshooting and FAQ

**Common Issues:**

- **Permission denied on mounted volumes:**
*Solution: Adjust directory ownership or permissions on the host.*
- **Port conflicts:**
*Solution: Change `SINGULARITY_PORT` in your `.env` file.*
- **Database connection errors:**
*Solution: Ensure DB service is healthy and credentials match.*

**FAQ:**

- How do I update the Singularity image?
  `docker-compose pull && docker-compose up -d`
- Where to get help?
  - [Singularity GitHub Issues](https://github.com/data-preservation-programs/singularity/issues)
  - [Filecoin Community Forums](https://discuss.filecoin.io/)
  - [Singularity Community on the Filecoin Slack](https://filecoinproject.slack.com/archives/C05JABREATH)

---

## Additional Resources

- [Singularity Documentation](https://data-programs.gitbook.io/singularity)
- [Singularity GitHub Repository](https://github.com/data-preservation-programs/singularity)
- [Filecoin Docs](https://docs.filecoin.io/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

## Conclusion

With this setup, you’re ready to preserve and onboard critical datasets to the Filecoin network using Singularity and Docker. This approach ensures your data remains accessible, secure, and reproducible—empowering open science for years to come.

---

**Have suggestions or improvements?**
*Contribute to this guide or share your feedback in an [issue](https://github.com/easierdata/Singularity/issues)!*
