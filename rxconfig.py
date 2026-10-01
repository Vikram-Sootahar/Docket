import reflex as rx

config = rx.Config(
    app_name="Docket",
    backend_host="127.0.0.1",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ]
)