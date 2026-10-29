
const PARTIAL_BASE = "/static/partials/";

export async function loadPartial(container, filename) {
    if (!container) {
        throw new Error(`HTML parçası için kapsayıcı bulunamadı: ${filename}`);
    }

    if (!/^[a-z0-9-]+\.html$/i.test(filename)) {
        throw new Error(`Geçersiz HTML parçası adı: ${filename}`);
    }

    const response = await fetch(
        `${PARTIAL_BASE}${encodeURIComponent(filename)}`,
        { cache: "no-cache" }
    );

    if (!response.ok) {
        throw new Error(
            `${filename} yüklenemedi (HTTP ${response.status}).`
        );
    }

    const html = await response.text();

    if (!html.trim()) {
        throw new Error(`${filename} dosyası boş.`);
    }

    container.innerHTML = html;
    return container;
}

export async function loadPartials(partials) {
    const results = await Promise.allSettled(
        partials.map(({ target, file }) => {
            const container =
                typeof target === "string"
                    ? document.querySelector(target)
                    : target;

            return loadPartial(container, file);
        })
    );

    const errors = results
        .map((result, index) => ({
            result,
            partial: partials[index],
        }))
        .filter(({ result }) => result.status === "rejected");

    if (errors.length > 0) {
        for (const { result, partial } of errors) {
            console.error(
                `HTML parçası yüklenemedi: ${partial.file}`,
                result.reason
            );
        }

        throw new Error(`${errors.length} HTML parçası yüklenemedi.`);
    }
}
