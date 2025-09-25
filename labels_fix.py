#!/usr/bin/env python3
"""Backward-compatible CLI wrapper around the label conversion library."""

from __future__ import annotations

import argparse

from label_converter import ConversionConfig, convert_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rogne la droite, tourne et impose 2 étiquettes par page.",
    )
    parser.add_argument("input", help="PDF d'entrée")
    parser.add_argument("output", help="PDF de sortie")
    parser.add_argument(
        "--left-ratio",
        type=float,
        default=None,
        help="Part de la largeur à garder à gauche (0–1]. Par défaut, détectée automatiquement.",
    )
    parser.add_argument(
        "--auto-left-min",
        type=float,
        default=0.45,
        help="Ratio minimal lorsque la largeur est détectée automatiquement",
    )
    parser.add_argument(
        "--auto-left-margin",
        type=float,
        default=8.0,
        help="Marge supplémentaire (en pixels à la résolution d'analyse) ajoutée à droite lors de la détection automatique",
    )
    parser.add_argument(
        "--auto-left-gap",
        type=float,
        default=25.0,
        help="Largeur minimale (en pixels à la résolution d'analyse) d'une zone blanche pour identifier la séparation",
    )
    parser.add_argument("--rotate", type=int, default=90, help="Rotation appliquée à chaque étiquette (0/90/180/270)")
    parser.add_argument(
        "--page",
        default="a4",
        help="a4, letter, ou LARGExHAUTEUR en points (ex: 595x842)",
    )
    parser.add_argument("--margin", type=float, default=12.0, help="Marge extérieure (pt)")
    parser.add_argument(
        "--fit",
        choices=["cover", "contain"],
        default="contain",
        help='Stratégie de redimensionnement ("contain" préserve l\'étiquette entière)'
    )
    parser.add_argument("--scale", type=float, default=2.0, help="Zoom global supplémentaire")
    parser.add_argument(
        "--fill-width",
        dest="fill_width",
        action="store_true",
        default=True,
        help="Tenter d'utiliser toute la largeur disponible lorsque c'est possible (défaut)",
    )
    parser.add_argument(
        "--no-fill-width",
        dest="fill_width",
        action="store_false",
        help="Ne pas forcer le remplissage complet de la largeur (comportement historique)",
    )
    parser.add_argument(
        "--halign",
        choices=["auto", "left", "center", "right"],
        default="auto",
        help="Alignement horizontal dans la zone cible (auto centre sauf débordement, ensuite colle à gauche)",
    )
    parser.add_argument(
        "--halign-offset",
        type=float,
        default=-6.0,
        help="Décalage horizontal supplémentaire en points après alignement (négatif = vers la gauche)",
    )
    parser.add_argument(
        "--halign-bleed",
        type=float,
        default=30.0,
        help="Autorise l'étiquette à dépasser la marge horizontale jusqu'à cette valeur (pt)",
    )
    parser.add_argument("--debug-boxes", action="store_true", help="Dessine les cadres de debug")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = ConversionConfig(
        left_ratio=args.left_ratio,
        auto_left_min=args.auto_left_min,
        auto_left_margin=args.auto_left_margin,
        auto_left_gap=args.auto_left_gap,
        rotate=args.rotate,
        page=args.page,
        margin=args.margin,
        fit=args.fit,
        scale=args.scale,
        fill_width=args.fill_width,
        halign=args.halign,
        halign_offset=args.halign_offset,
        halign_bleed=args.halign_bleed,
        debug_boxes=args.debug_boxes,
    )

    convert_pdf(args.input, args.output, cfg)


if __name__ == "__main__":
    main()
