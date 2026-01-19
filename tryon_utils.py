import cv2
import numpy as np

def simple_tryon(person_path, cloth_path, output_path):
    person = cv2.imread(person_path)
    cloth = cv2.imread(cloth_path, cv2.IMREAD_UNCHANGED)

    if person is None or cloth is None:
        raise ValueError("Resimler okunamadı")

    ph, pw, _ = person.shape

    # Elbiseyi gövdeye göre ölçekle
    target_width = int(pw * 0.5)
    scale = target_width / cloth.shape[1]
    new_size = (
        int(cloth.shape[1] * scale),
        int(cloth.shape[0] * scale)
    )
    cloth = cv2.resize(cloth, new_size)

    x = pw // 2 - cloth.shape[1] // 2
    y = int(ph * 0.25)

    overlay = person.copy()

    for i in range(cloth.shape[0]):
        for j in range(cloth.shape[1]):
            if x + j >= pw or y + i >= ph:
                continue

            if cloth.shape[2] == 4:
                alpha = cloth[i, j, 3] / 255.0
                overlay[y+i, x+j] = (
                    alpha * cloth[i, j, :3] +
                    (1 - alpha) * overlay[y+i, x+j]
                )
            else:
                overlay[y+i, x+j] = cloth[i, j]

    cv2.imwrite(output_path, overlay)
