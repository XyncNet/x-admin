function processElement(element) {
    $(".field-list-btn-add", element).each(function () {
        const el = $(this);
        el.on("click", function () {
            const field = el.closest(".field-list");
            const baseName = field.attr("id");
            const idx = field.children("#" + $.escapeSelector(baseName) + "-next-index").val();
            const template = $(field.children(".template").text());

            function update_attr(el, attr) {
                $(`[${attr}]`, el).each(function () {
                    const sfx = this.name.endsWith('[]') ? '[]' : ''
                    $(this).attr(attr, baseName + "." + idx + sfx);
                });
            }
            update_attr(template, "id");
            update_attr(template, "name");
            update_attr(template, "for");

            template.appendTo(field.children(".list-container"));
            field.children("#" + $.escapeSelector(baseName) + "-next-index").val(parseInt(idx) + 1);
            processElement(template);
            $("input:first", template).focus();
        });
    });

    $("button.field-list-btn-remove", element).each(function () {
        const el = $(this);
        el.on("click", function () {
            el.closest(".field-list-item").remove();
        });
    });
}

processElement(document);
